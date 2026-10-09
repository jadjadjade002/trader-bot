"""Fee-aware, position-ID evaluation of the frozen V23 native MT5 experiment."""
from __future__ import annotations
import argparse
import csv
import hashlib
import importlib.util
import json
import math
import re
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'reports/v23_backtest_20261004'
spec = importlib.util.spec_from_file_location('native_rows', ROOT/'scripts/analyze_v17_report.py')
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)

def finite(value):
    result = float(str(value).replace(' ', '').replace(',', ''))
    if not math.isfinite(result):
        raise ValueError('Nonfinite monetary value')
    return result

def timestamp(ms):
    # MQL epoch encodes broker clock; this is formatting, not a UTC conversion claim.
    return datetime.fromtimestamp(int(ms)/1000, timezone.utc).replace(tzinfo=None)

def csv_rows(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def report_rows(path):
    raw = Path(path).read_bytes()
    parser = native.Rows()
    parser.feed(raw.decode('utf-16' if raw[:2] in (b'\xff\xfe',b'\xfe\xff') else 'utf-8-sig'))
    metrics = {}
    for row in parser.rows:
        for i, value in enumerate(row[:-1]):
            if value.endswith(':'): metrics[value[:-1]] = row[i+1]
    return metrics, parser.rows

def parse_deals(rows, *, native_end_tickets=frozenset()):
    required = {'ticket','position','time_msc','type','entry','reason','magic','symbol','volume','price','profit','commission','swap','fee','comment'}
    if rows and not required <= set(rows[0]): raise ValueError('Deal schema incomplete')
    if len(native_end_tickets) > 1 or any(type(t) is not int or t <= 0 for t in native_end_tickets):
        raise ValueError('Invalid verified native-end ticket whitelist')
    active, trades, cash, used_native_end = {}, [], [], set()
    for row in sorted(rows,key=lambda d:(int(d['time_msc']),int(d['ticket']))):
        d = dict(row)
        for k in ('ticket','position','time_msc','type','entry','reason','magic'): d[k]=int(d[k])
        for k in ('volume','price','profit','commission','swap','fee'): d[k]=finite(d[k])
        d['net'] = sum(d[k] for k in ('profit','commission','swap','fee'))
        if d['type'] not in (0,1):
            cash.append(d)
            continue
        verified_end = (d['ticket'] in native_end_tickets and d['magic']==0
                        and d['reason']==0 and d['entry']==1 and d['comment']=='end of test')
        if d['symbol']!='XAUUSD' or (d['magic']!=992300 and not verified_end):
            raise ValueError('Foreign trading deal')
        if verified_end:
            if d['ticket'] in used_native_end: raise ValueError('Duplicate native-end ticket')
            used_native_end.add(d['ticket'])
        p=d['position']
        if d['entry']==0:
            if p in active or active: raise ValueError('Unsupported concurrent/add-on entry')
            active[p]=dict(position=p,open_msc=d['time_msc'],direction='buy' if d['type']==0 else 'sell',
                           entry_price=d['price'],volume=d['volume'],remaining=d['volume'],net=d['net'],
                           profit=d['profit'],commission=d['commission'],swap=d['swap'],fee=d['fee'],deals=[d])
        elif d['entry']==1:
            if p not in active: raise ValueError('Exit without matching position')
            t=active[p]
            if (t['direction']=='buy') == (d['type']==0): raise ValueError('Exit side mismatch')
            t['remaining']-=d['volume']
            if t['remaining'] < -1e-8: raise ValueError('Exit volume exceeds entry')
            for k in ('net','profit','commission','swap','fee'): t[k]+=d[k]
            t['deals'].append(d)
            if t['remaining']<1e-8:
                t.update(close_msc=d['time_msc'],exit_price=d['price'],exit_reason=d['reason'],comment=d['comment'],
                         open=timestamp(t['open_msc']).isoformat(),close=timestamp(d['time_msc']).isoformat())
                trades.append(t);del active[p]
        else: raise ValueError('Unsupported reversal/out-by deal')
    if active: raise ValueError('Unclosed position at export')
    if used_native_end != set(native_end_tickets): raise ValueError('Unused verified native-end ticket')
    return trades,cash

def bucket(trades):
    pnl=[t['net'] for t in trades]
    pos=sum(x for x in pnl if x>1e-8); neg=-sum(x for x in pnl if x < -1e-8)
    return dict(trades=len(trades),wins=sum(x>1e-8 for x in pnl),losses=sum(x < -1e-8 for x in pnl),
                zero=sum(abs(x)<=1e-8 for x in pnl),net=round(sum(pnl),2),
                net_profit_factor=round(pos/neg,4) if neg else None,
                pf_status='finite' if neg else 'no_losses' if pos else 'no_trades_or_zero_only',
                win_rate_pct=round(100*sum(x>1e-8 for x in pnl)/len(pnl),2) if pnl else None,
                **{k:round(sum(t[k] for t in trades),2) for k in ('profit','commission','swap','fee')})

def evaluate(run):
    run=Path(run); meta=json.loads((run/'metadata.json').read_text(encoding='utf-8-sig'));name=meta['name']
    if meta.get('exit_code')!=0 or meta.get('runtime_drift'): raise ValueError('Unsuccessful native run')
    metrics,_=report_rows(run/f'{name}.htm')
    if metrics.get('History Quality')!='100% real ticks': raise ValueError('Not full native real-tick quality')
    if finite(metrics['Ticks'])<=0 or finite(metrics['Bars'])<=0: raise ValueError('Empty native test')
    spec_rows=csv_rows(run/f'{name}_spec.csv'); specs={r['key']:r['value'] for r in spec_rows}
    if specs.get('history_export_ok') not in ('true','1'): raise ValueError('History export failed')
    deals=csv_rows(run/f'{name}_deals.csv'); trades,cash=parse_deals(deals)
    result=bucket(trades)
    if result['trades']!=int(finite(metrics['Total Trades'])): raise ValueError('Trade-count reconciliation failed')
    if abs(result['net']-finite(metrics['Total Net Profit']))>.021: raise ValueError('Native net reconciliation failed')
    if abs(finite(specs['final_balance'])-meta['deposit']-result['net'])>.021: raise ValueError('Final balance reconciliation failed')
    if len(cash)!=1 or cash[0]['type']!=2 or abs(cash[0]['net']-meta['deposit'])>.021:
        raise ValueError('Unsupported nontrade cash adjustment')
    equity=csv_rows(run/f'{name}_equity.csv')
    if not equity: raise ValueError('Equity telemetry missing')
    observations={r['month'][:4]+'-'+r['month'][4:]:r for r in equity}
    logs='\n'.join(p.read_text(encoding='utf-8-sig') for p in sorted((run/'logs').glob('*.txt')))
    if 'Test passed in' not in logs: raise ValueError('Native completion evidence missing')
    issues=[line for line in logs.splitlines() if re.search(r'(?:no real ticks|generated ticks|ticks?[^\n]*(?:discarded|replaced|missing)|history[^\n]*error|file opening or reading error)',line,re.I)]
    if issues: raise ValueError('Tick/history quality warning: '+issues[0])
    early=meta['from']=='2026.05.01' and timestamp(specs['last_tick']).strftime('%Y-%m-%d')!='2026-09-30'
    exhausted=early and meta['deposit']==70 and any(t['exit_reason']==6 for t in trades) and bool(re.search('stop out|stopout',logs,re.I))
    if early and not exhausted: raise ValueError('Unexplained early simulation termination')
    monthly={};streak=0;max_streak=0
    for month in ('2026-05','2026-06','2026-07','2026-08','2026-09'):
        selected=[t for t in trades if t['close'].startswith(month)]
        b=bucket(selected);b['opening_loss_streak']=streak;local_max=streak
        for t in selected:
            streak=streak+1 if t['net'] < -1e-8 else 0
            local_max=max(local_max,streak);max_streak=max(max_streak,streak)
        b['max_ongoing_loss_streak']=local_max;b['closing_loss_streak']=streak
        start=datetime.strptime(month,'%Y-%m')
        b['carried_in_positions']=sum(timestamp(t['open_msc'])<start<=timestamp(t['close_msc']) for t in trades)
        next_month=start.replace(year=start.year+1,month=1) if start.month==12 else start.replace(month=start.month+1)
        b['entry_count']=sum(t['open'][:7]==month for t in trades)
        b['carried_out_positions']=sum(timestamp(t['open_msc'])<next_month<=timestamp(t['close_msc']) for t in trades)
        b['cross_month_closed_positions']=sum(t['open'][:7]!=month for t in selected)
        b['forced_end_exits']=sum('end of test' in t['comment'].lower() for t in selected)
        b['forced_end_net']=round(sum(t['net'] for t in selected if 'end of test' in t['comment'].lower()),2)
        if month in observations:
            obs=observations[month]
            b['observed_equity_dd_sampled']=round(finite(obs['observed_equity_dd']),2)
            b['observed_equity_dd_pct_sampled']=round(finite(obs['observed_equity_dd_pct']),3)
            b['first_observed_tick']=timestamp(obs['first_msc']).isoformat()
            b['last_observed_tick']=timestamp(obs['last_msc']).isoformat()
            b['callback_ticks']=int(obs['observed_ticks'])
        elif meta['from']=='2026.05.01' and not exhausted: raise ValueError('Missing observed month '+month)
        elif exhausted:b['simulation_inactive_after_exhaustion']=True
        monthly[month]=b
    if meta['from']=='2026.05.01':
        if not exhausted and timestamp(specs['last_tick']).strftime('%Y-%m-%d')!='2026-09-30': raise ValueError('September30 tick coverage missing')
        if timestamp(specs['first_tick']).strftime('%Y-%m')!='2026-05': raise ValueError('May coverage missing')
    result.update(name=name,variant=meta['variant'],deposit=meta['deposit'],monthly=monthly,max_net_loss_streak=max_streak,
                  native=metrics,broker_specs=specs,forced_end_exits=sum('end of test' in t['comment'].lower() for t in trades),
                  stopout_positions=sum(t['exit_reason']==6 for t in trades),observed_dd_note='callback sampled estimate; NOT a proven lower bound relative to native statistics; cause of discrepancy unknown; native overall equity DD authoritative',
                  trades_detail=trades,metadata=meta,early_capital_exhaustion=exhausted,completed_to=timestamp(specs['last_tick']).isoformat())
    # Agent+terminal logs can duplicate messages. Gate count uses raw ledger for exact candidate outcomes.
    raw=csv_rows(run/f'{name}_raw.csv')
    result['candidate_gate_counts']=dict(Counter(r['gate'] for r in raw))
    result['candidate_order_attempts']=sum(r['order_attempt'] in ('true','1') for r in raw)
    result['margin_gate_count']=result['candidate_gate_counts'].get('margin',0)
    result['invalid_stops_count']=sum(int(r['retcode'])==10016 and r['order_attempt'] in ('true','1') for r in raw)
    result['order_retcode_counts']=dict(Counter(r['retcode'] for r in raw if r['order_attempt'] in ('true','1')))
    result['native_equity_dd']=finite(metrics['Equity Drawdown Maximal'].split('(')[0])
    result['observed_overall_dd_minus_native']=round(finite(specs['observed_overall_equity_dd'])-result['native_equity_dd'],2)
    return result

def parity(original,harness):
    a=Path(original);b=Path(harness)
    am=json.loads((a/'metadata.json').read_text(encoding='utf-8-sig'));bm=json.loads((b/'metadata.json').read_text(encoding='utf-8-sig'))
    ma,ra=report_rows(a/f"{am['name']}.htm");mb,rb=report_rows(b/f"{bm['name']}.htm")
    def economics(rows):
        # Native Orders and Deals tables; retain direction, volume, prices, SL/TP, time and reason/comment.
        return [r for r in rows if any(x in ('buy','sell') for x in r) and r[0].startswith('2026.')]
    if economics(ra)!=economics(rb): raise ValueError('Native ordered economic sequence differs')
    for key in ('Total Trades','Total Net Profit','Ticks','Bars','History Quality','Equity Drawdown Maximal','Balance Drawdown Maximal'):
        if ma[key]!=mb[key]: raise ValueError('Parity metric differs: '+key)
    for key in ('terminal','agent','protocol'):
        if am['sha256'][key]!=bm['sha256'][key]: raise ValueError('Parity artifact mismatch '+key)
    def breakers(folder):
        text='\n'.join(p.read_text(encoding='utf-8-sig') for p in sorted((folder/'logs').glob('*.txt')))
        return sorted(re.findall(r'(2026\.\d\d\.\d\d \d\d:\d\d:\d\d\s+.*CIRCUIT BREAKER TRIGGERED:[^\r\n]+)',text))
    if breakers(a)!=breakers(b): raise ValueError('Breaker sequence differs')
    return dict(passed=True,original=str(a),harness=str(b),trades=int(ma['Total Trades']),net=finite(ma['Total Net Profit']),
                economic_rows=len(economics(ra)),resolution='native HTML order/deal timestamps (seconds); harness additionally exports milliseconds')

def candidate_comparison(baseline,closeback):
    def rows(run):
        name=run['name'];folder=BASE/'runs'/name
        return {r['bar']:r for r in csv_rows(folder/f'{name}_raw.csv')}
    a=rows(baseline);b=rows(closeback)
    original={k for k,r in a.items() if int(r['original'])!=0 and r['gate']!='attach'}
    rejection={k for k,r in a.items() if int(r['closeback'])!=0 and r['gate']!='attach'}
    # All predicate sets use the SAME baseline snapshot. Callback availability is separate.
    removed=original-rejection;matched=[];unknown=[]
    attempt_by_deal={int(r['deal_ticket']):r for r in a.values() if int(r['deal_ticket'])>0}
    for t in baseline['trades_detail']:
        row=attempt_by_deal.get(t['deals'][0]['ticket'])
        if row is None:unknown.append(t['position']);continue
        if int(row['closeback'])==0:matched.append(t)
    return dict(common=len(original&rejection),removed=len(removed),new=len(rejection-original),
                baseline_filled_failing_closeback=bucket(matched),unmatched_baseline_positions=unknown,
                callback_bars_only_baseline=len(set(a)-set(b)),callback_bars_only_closeback=len(set(b)-set(a)),
                classified_from='baseline all-bar snapshots only; successful CTrade ResultDeal joins entry ticket',
                note='Counterfactual predicate attribution only; occupancy/breaker/new-entry paths change, so removed PnL is not predicted strategy improvement.')

def audit_probe(run):
    run=Path(run);meta=json.loads((run/'metadata.json').read_text(encoding='utf-8-sig'));name=meta['name']
    metrics,_=report_rows(run/f'{name}.htm')
    if meta.get('exit_code')!=0 or meta.get('runtime_drift') or metrics.get('History Quality')!='100% real ticks':raise ValueError('Market probe failed')
    daily=csv_rows(run/f'{name}_daily.csv');gaps=csv_rows(run/f'{name}_gaps.csv')
    if not daily or daily[0]['day']!='2026.05.01' or daily[-1]['day']!='2026.09.30':raise ValueError('Probe date endpoints missing')
    if sum(int(r['ticks']) for r in daily)!=int(finite(metrics['Ticks'])):raise ValueError('Probe ticks do not reconcile')
    dates={r['day'] for r in daily};day=datetime(2026,5,1);missing=[]
    while day<datetime(2026,10,1):
        if day.weekday()<5 and day.strftime('%Y.%m.%d') not in dates:missing.append(day.strftime('%Y-%m-%d'))
        day+=timedelta(days=1)
    if missing:raise ValueError('Missing weekday sessions require broker holiday review: '+','.join(missing))
    if gaps:raise ValueError('Unexplained intraday tick gaps >300s require review')
    issues=csv_rows(run/f'{name}_minute_issues.csv')
    contradictory=[r for r in issues if int(r['quote_ticks'])>0 and int(r['bar_present'])==0]
    if contradictory:raise ValueError('Quote ticks present but missing M1 bars: '+str(contradictory[:8]))
    logs='\n'.join(p.read_text(encoding='utf-8-sig') for p in (run/'logs').glob('*.txt'))
    warnings=[line for line in logs.splitlines() if re.search(r'no real ticks|generated ticks|ticks?[^\n]*(?:discarded|replaced|missing)|history[^\n]*error',line,re.I)]
    if warnings:raise ValueError('Probe data warning: '+warnings[0])
    months={}
    for row in daily:
        month=row['day'][:7].replace('.','-');v=months.setdefault(month,dict(days=0,ticks=0,m1_bars=0))
        v['days']+=1;v['ticks']+=int(row['ticks']);v['m1_bars']+=int(row['m1_bars'])
    return dict(passed=True,acceptance='bounded common-source native diagnostic; strict gap-free validation NOT passed',native=metrics,monthly=months,days=len(daily),intraday_gaps_over_300s=gaps,minute_issues=issues,
                daily=daily,broker_schedule=csv_rows(run/f'{name}_sessions.csv'),note='Broker weekdays and endpoints verified; native Model4 real ticks, no substitution warnings. Callback probe has no orders or delay.')

def main():
    p=argparse.ArgumentParser();p.add_argument('--runs',nargs='+');p.add_argument('--parity',nargs=2);p.add_argument('--probe');p.add_argument('--output',required=True)
    args=p.parse_args();out={}
    if args.parity: out['parity']=parity(*(BASE/'runs'/x for x in args.parity))
    if args.probe:out['market_probe']=audit_probe(BASE/'runs'/args.probe)
    if args.runs:
        results=[evaluate(BASE/'runs'/x) for x in args.runs]
        hashes={(r['metadata']['sha256']['terminal'],r['metadata']['sha256']['agent'],r['metadata']['sha256']['binary'],r['metadata']['sha256']['protocol']) for r in results}
        if len(hashes)!=1: raise ValueError('Cross-run frozen artifacts differ')
        market={(r['native']['Ticks'],r['native']['Bars']) for r in results if not r['early_capital_exhaustion']}
        if len(market)!=1: raise ValueError('Cross-run market coverage differs')
        if args.probe:
            probe=out['market_probe']['native']
            if market!={(probe['Ticks'],probe['Bars'])}:raise ValueError('Strategy data differs from independent full-period probe')
        cache=[json.loads((BASE/'runs'/r['name']/'tick_cache_manifest.json').read_text(encoding='utf-8-sig')) for r in results]
        if any(c!=cache[0] for c in cache[1:]): raise ValueError('Post-sync tick caches differ')
        out['runs']=results;out['candidate_comparisons']={}
        for deposit in {r['deposit'] for r in results}:
            pair={r['variant']:r for r in results if r['deposit']==deposit}
            if 'fade' in pair and 'closeback' in pair: out['candidate_comparisons'][str(deposit)]=candidate_comparison(pair['fade'],pair['closeback'])
    Path(args.output).write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    summary={k:v for k,v in out.items() if k not in ('runs','market_probe','candidate_comparisons')}
    if 'runs' in out:summary['runs']=[{x:r[x] for x in ('name','trades','net','net_profit_factor')} for r in out['runs']]
    if 'market_probe' in out:summary['market_probe']={k:out['market_probe'][k] for k in ('passed','days','monthly','minute_issues')}
    print(json.dumps(summary,ensure_ascii=False,default=str))

if __name__=='__main__':main()
