"""Parse native MT5 reports; count complete single-position round trips, including costs.

Free standard-library tooling. Reject concurrent positions or partial reversals: an
HTML deal table does not expose position IDs sufficiently to group those safely.
Zero-profit closes are not wins. End-of-test liquidations are reported explicitly.
"""
import argparse
import json
import math
import re
from datetime import datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path


class Rows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.row, self.cell = [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self.row = []
        if tag in ('td', 'th'):
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.row is not None and self.cell is not None:
            self.row.append(' '.join(''.join(self.cell).split()))
            self.cell = None
        if tag == 'tr' and self.row is not None:
            self.rows.append(self.row)
            self.row = None


def number(text):
    return float(text.replace(' ', '').replace(',', ''))


def wilson(wins, total):
    if not total:
        return [0, 100]
    p, z = wins / total, 1.95996398454
    center = (p + z*z/(2*total)) / (1+z*z/total)
    half = z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/(1+z*z/total)
    return [round(100*(center-half), 2), round(100*(center+half), 2)]


def analyze(path, start_hour=18, end_hour=2):
    raw = Path(path).read_bytes()
    content = raw.decode('utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig')
    parser = Rows()
    parser.feed(content)
    metrics = {}
    for row in parser.rows:
        for i, value in enumerate(row[:-1]):
            if value.endswith(':'):
                metrics[value[:-1]] = row[i+1]
    closed, current, deal_table = [], None, False
    for row in parser.rows:
        if row == ['Deals']:
            deal_table = True
            continue
        if not deal_table or len(row) != 13 or row[3] not in ('buy', 'sell'):
            continue
        stamp = datetime.strptime(row[0], '%Y.%m.%d %H:%M:%S')
        volume = number(row[5])
        net = sum(number(row[i]) for i in (8, 9, 10))
        if row[4] == 'in':
            if current is not None:
                raise ValueError('Concurrent entries: export position IDs instead of using this parser.')
            current = dict(open=stamp, direction=row[3], volume=volume, remaining=volume,
                           entry=number(row[6]), net=net)
        elif row[4] == 'out':
            if current is None:
                raise ValueError('Exit without entry')
            current['net'] += net
            current['remaining'] -= volume
            if current['remaining'] < -1e-7:
                raise ValueError('Exit exceeds volume')
            if current['remaining'] < 1e-7:
                current.update(close=stamp, exit=number(row[6]), comment=row[12])
                closed.append(current)
                current = None
        else:
            raise ValueError('Unsupported deal direction ' + row[4])
    if current is not None:
        raise ValueError('Report has an unclosed position; report floating equity separately.')
    native_total = int(metrics.get('Total Trades', '0').replace(' ', ''))
    if len(closed) != native_total:
        raise ValueError(f'Round-trip count {len(closed)} differs from MT5 {native_total}')
    net = sum(t['net'] for t in closed)
    if abs(net-number(metrics['Total Net Profit'])) > .021:
        raise ValueError('Net PnL does not reconcile to native report')
    wins = sum(t['net'] > .00001 for t in closed)
    # Count every complete weekday overnight window, including zero-trade nights.
    dates = re.findall(r'\d{4}\.\d{2}\.\d{2}', metrics['Period'])
    begin, end = (datetime.strptime(d, '%Y.%m.%d') for d in dates[-2:])
    sessions = {}
    day = begin
    while day < end:
        opening = day.replace(hour=start_hour)
        closing = day.replace(hour=end_hour) + timedelta(days=int(end_hour <= start_hour))
        if day.weekday() < 5 and opening >= begin and closing <= end:
            sessions[day.strftime('%Y-%m-%d')] = dict(trades=0, wins=0, net=0.0, carried_past_wake=0)
        day += timedelta(days=1)
    for trade in closed:
        stamp = trade['open']
        in_window = (start_hour <= stamp.hour < end_hour if start_hour < end_hour
                     else stamp.hour >= start_hour or stamp.hour < end_hour)
        if not in_window:
            continue
        date = stamp - timedelta(days=int(stamp.hour < end_hour and end_hour <= start_hour))
        key = date.strftime('%Y-%m-%d')
        if key in sessions:
            bucket = sessions[key]
            wake = datetime.strptime(key, '%Y-%m-%d').replace(hour=end_hour)
            wake += timedelta(days=int(end_hour <= start_hour))
            if trade['close'] > wake:
                bucket['carried_past_wake'] += 1
                continue
            bucket['trades'] += 1
            bucket['wins'] += int(trade['net'] > .00001)
            bucket['net'] += trade['net']
    for bucket in sessions.values():
        bucket['net'] = round(bucket['net'], 2)
        bucket['win_rate_pct'] = round(100*bucket['wins']/bucket['trades'], 2) if bucket['trades'] else None
        bucket['target_met'] = (10 <= bucket['trades'] <= 20 and bucket['win_rate_pct'] >= 80 and bucket['net'] > 0)
    return dict(
        report=str(Path(path).resolve()), native=metrics, trades=len(closed), wins=wins,
        win_rate_pct=round(100*wins/len(closed), 2) if closed else None,
        win_rate_wilson_95_pct=wilson(wins,len(closed)), net=round(net,2),
        mean_trades_per_overnight=round(sum(b['trades'] for b in sessions.values())/len(sessions),2) if sessions else None,
        full_weekday_windows=len(sessions), nights_meeting_all_targets=sum(b['target_met'] for b in sessions.values()),
        overnight_broker_hours=f'{start_hour:02d}:00-{end_hour:02d}:00', sessions=sessions,
        forced_test_end_exits=sum('end of test' in t['comment'].lower() for t in closed),
        independent_trial_assumption='Wilson interval assumes independent trades; correlated scalps can make it overconfident',
        closed=[{k:(v.isoformat() if isinstance(v, datetime) else round(v,6) if isinstance(v,float) else v)
                 for k,v in t.items()} for t in closed])


if __name__ == '__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('report')
    ap.add_argument('--output')
    args=ap.parse_args()
    result=analyze(args.report)
    if args.output:
        Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('native','closed','sessions')},indent=2))
