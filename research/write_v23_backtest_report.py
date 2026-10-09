"""Render reviewed native V23 results; no fitting or strategy parameter changes."""
from pathlib import Path
from datetime import datetime
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'reports/v23_backtest_20261004'
d=json.loads((BASE/'comparison.json').read_text(encoding='utf-8'))
runs=d['runs']
labels={'fade':'Fade เดิม','momentum':'Momentum','closeback':'Fade ปิดกลับในกรอบ'}
english={'fade':'Original fade','momentum':'Momentum','closeback':'Closeback fade'}
colors={'fade':'#D84A4A','momentum':'#497AC2','closeback':'#9B65B6'}

fig,axes=plt.subplots(2,1,figsize=(11,7),sharex=True,layout='constrained')
for i,deposit in enumerate((10000,70)):
    ax=axes[i]
    for r in (x for x in runs if x['deposit']==deposit):
        x=[datetime(2026,5,1)];y=[0 if deposit==10000 else 70];balance=y[0]
        for t in r['trades_detail']:
            balance+=t['net'];x.append(datetime.fromisoformat(t['close']));y.append(balance)
        x.append(datetime(2026,9,30,23));y.append(balance)
        ax.step(x,y,where='post',label=english[r['variant']],color=colors[r['variant']],lw=1.5)
    ax.axhline(0 if deposit==10000 else 70,color='#777777',ls=':',lw=1)
    ax.grid(alpha=.18);ax.legend(ncol=3,loc='best',fontsize=9)
    ax.set_ylabel('Closed-trade P/L ($)' if deposit==10000 else 'Closed-trade balance ($)')
    ax.set_title('$10,000 diagnostic capital' if deposit==10000 else '$70 feasibility capital — flat sections: no executed trades',loc='left',fontsize=11)
axes[-1].xaxis.set_major_locator(mdates.MonthLocator())
axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%b 2026'))
axes[-1].set_xlim(datetime(2026,5,1),datetime(2026,9,30,23))
fig.suptitle('V23 native backtest | fixed 0.01 lot | May–September 2026',fontsize=14)
fig.supxlabel('Broker history clock; curves exclude floating P/L. Same source history contains eight quote-free minutes.',fontsize=8)
fig.savefig(BASE/'balance_curves.png',dpi=180)
plt.close(fig)

def link(path):return Path(path).resolve().as_posix()
def cell(value):return '—' if value is None else str(value)
def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join('---' for _ in headers)+'|']+['| '+' | '.join(str(x) for x in row)+' |' for row in rows])

out=['# V23 — Native backtest 5 เดือน: 1 พ.ค.–30 ก.ย. 2026','',
     '**ทั้ง 3 policy ขาดทุนที่ทุน $10,000; PF < 1. ทุน $70 เปิดต่อไม่ได้หลัง balance ลดจนติด margin gate. ยังไม่มีรุ่นผ่านด้านกำไรจากผลชุดนี้.**','',
     'ทดสอบ continuous ไม่ reset รายเดือน: XAUUSD M1, MetaQuotes-Demo, MT5 terminal/tester build 6238, Model 4, execution delay 200 ms, leverage 1:200, lot คงที่ 0.01. ทุน $10,000 ใช้ตรวจผลสัญญาณโดยลดข้อจำกัดทุน; ทุน $70 ใช้ตรวจความเป็นไปได้ด้วยเงินทุนจำลองขนาดเล็ก. ผล $10,000 ไม่ใช่ผลที่บัญชี $70 จะทำได้.','',
     'คงกฎ V23: session guard ปิด, spread guard ปิด, margin guard เปิด, hard SL เปิด, Donchian 20, ATR 14, SL=max(1.5 ATR,150 points), TP=2R, time exit=60 M1 bars, circuit breaker=4 gross-deal losses/90 นาที. ไม่แก้ execution/risk ใน EA จริง และไม่ optimize หลังเห็นผล.','',
     table(['ทุน','Policy','ออเดอร์ปิด','Net USD','Net PF','Native equity DD สูงสุด','Balance จบ'],[
         [f"${r['deposit']:,.0f}",labels[r['variant']],f"{r['trades']:,}",f"{r['net']:,.2f}",f"{r['net_profit_factor']:.4f}",r['native']['Equity Drawdown Maximal'],f"{float(r['broker_specs']['final_balance']):,.2f}"] for r in runs]),'',
     'ไม่มี StopOut และไม่มี end-of-test forced exit ทุกชุด. ทุกชุดประมวลผลถึง 30 ก.ย.; จำนวนไม้ที่ลดเหลือศูนย์ในทุน $70 เกิดจาก margin guard ไม่ใช่ข้อมูลหยุดหรือผลกำไรที่ดี. DD สูงสุดอาจเกินทุนเริ่ม เพราะ balance เคยเพิ่มก่อน drawdown.','',
     f"![Closed-trade balance curves]({link(BASE/'balance_curves.png')})",'',
     'กราฟใช้ balance จาก position ที่ปิดแล้ว ไม่รวม floating P/L. เส้นขั้นบันไดคงค่าระหว่างวันที่ไม่มี deal.','',
     '**จำนวนออเดอร์และกำไรเปลี่ยนอย่างไร**','',
     'ทุน $10,000: closeback ลด 2,987 → 1,436 ไม้ (-51.93%); net ขาดทุนลด $877.84 แต่ยังขาดทุน $464.50. Momentum ลดเหลือ 2,705 ไม้และยังขาดทุน $1,221.67. ค่าเฉลี่ย net/ไม้: Fade -$0.4494, Momentum -$0.4516, closeback -$0.3235. เปลี่ยนทิศหรือเพิ่มเงื่อนไขปิดกลับอย่างเดียวไม่สร้าง positive expectancy ใน configuration นี้.','',
     '**ผลรายเดือน — attrib ตามวันปิด position ใน broker clock**','']
for capital in (10000,70):
    selected=[r for r in runs if r['deposit']==capital]
    out.extend([f'ทุน ${capital:,.0f}. ในช่อง: ออเดอร์ / Net USD / Net PF. PF ของเดือนไม่มีไม้แสดง —.','',
      table(['เดือน']+[labels[r['variant']] for r in selected],[[month]+[f"{r['monthly'][month]['trades']} / {r['monthly'][month]['net']:+.2f} / {cell(r['monthly'][month]['net_profit_factor'])}" for r in selected] for month in ('2026-05','2026-06','2026-07','2026-08','2026-09')]),''])
out.extend(['ไม่มี position ข้ามเดือนและไม่มี forced-end net ในข้อมูลชุดนี้. JSON เก็บ entry count, carry-in/out, zero PnL, loss streak พร้อม state ข้ามเดือน.','',
    '**ทุน $70: สัญญาณยังมี แต่ margin ไม่พอ**','',
    table(['Policy','Margin blocks จริง','Last entry (broker clock)','Balance จบ','เหตุการณ์'],[
      [labels[r['variant']],f"{r['margin_gate_count']:,}",r['trades_detail'][-1]['open'],f"${float(r['broker_specs']['final_balance']):.2f}",'Simulation ครบ; หลังจากนั้นไม่มี entry สำเร็จ'] for r in runs if r['deposit']==70]),'',
    'CheckMargin บล็อกเมื่อ required margin > 70% ของ free margin. Lot 0.01 จึงไม่รักษาความสามารถเปิดไม้ตลอด 5 เดือนที่ทุนนี้. Momentum มีเพียง 1 ไม้ในเดือนมิถุนายน; closeback หยุดมี entry สำเร็จตั้งแต่เดือนพฤษภาคม. Native stopout level เป็น 30% แต่ไม่ถูกเรียกใช้ในการรันนี้.','',
    '**สิ่งที่บอกเรื่องการเข้าผิด**','',
    'Fade เดิมหา breakout + retest แท่งสีทิศเดิม แล้วกลับทิศ โดยไม่บังคับให้ราคาปิดกลับใน Donchian channel. Closeback ใช้ strict `DC_low < retestClose < DC_high` แทน candle-color gate; คง breakout, proximity 0.5 ATR และ Fade direction. จึงเปลี่ยนประชากรสัญญาณ ไม่ใช่ subset filter ของไม้เดิม.','',
    'บน raw bar ledger เดียวกัน: original candidates 7,984, common 2, removed 7,982, new closeback candidates 1,961. ทุก baseline filled entry 2,987 ไม้ไม่ผ่านเงื่อนไข closeback; รวม winners 909 และ losers 2,078. ไม่มี unmatched deal-ticket join. ถ้าตัดด้วยเงื่อนไขใหม่นี้ ย่อมตัดไม้ชนะเดิมด้วยทั้งหมด; ห้ามนำกำไร/ขาดทุนที่ตัดมาบวกเป็นกำไรของ strategy ใหม่ เพราะ occupancy/circuit breaker และไม้ใหม่เปลี่ยนเส้นทาง.','',
    'หลักฐานนี้ยืนยันว่า baseline ไม่รอ closeback confirmation. ไม่พิสูจน์ว่าทุกไม้แพ้เกิดจากวิเคราะห์ผิด หรือทุก continuation ควรถูก Fade. ทั้ง Fade และ Momentum policy ที่ทดสอบขาดทุน จึงสรุปไม่ได้ว่าเปลี่ยน sign อย่างเดียวแก้ปัญหา. ไม่ได้แยกสรุป profitability ของ BUY และ SELL subgroup.','',
    '**ต้นทุนและ execution**','',
    table(['ทุน / Policy','Commission','Swap','Fee','Invalid stops จริง','Net loss streak สูงสุด'],[
      [f"${r['deposit']:,.0f} / {labels[r['variant']]}",f"{r['commission']:.2f}",f"{r['swap']:.2f}",f"{r['fee']:.2f}",r['invalid_stops_count'],r['max_net_loss_streak']] for r in runs]),'',
    'Net = DEAL_PROFIT + DEAL_COMMISSION + DEAL_SWAP + DEAL_FEE ทั้ง entry และ exit รวมตาม POSITION_ID; กระทบยอด native net, monthly sum และ final balance ทุกชุด. Spread อยู่ใน native Bid/Ask execution แล้ว ไม่หักซ้ำ. Commission/Fee = 0 ใน broker model นี้ ไม่ยืนยันว่า broker production คิด 0. Delay 200 ms ไม่จำลอง live outliers 36–54 วินาทีที่พบใน audit เดิม.','',
    '**ข้อมูลและขอบเขต validation**','',
    'Native รายงาน `100% real ticks`; independent no-trade/no-delay probe นับได้ 58,118,739 ticks, 143,336 M1 bars, 109 weekday sessions. ทุก strategy run ใช้จำนวน ticks/bars และ post-sync cache hashes เดียวกัน. Probe ตรวจ minute tick counts เทียบ CopyRates timestamps; ไม่พบมี quote ticks แต่ M1 bar หาย.','',
    table(['ช่วง broker clock','Quote-free / bar-free นาที'],[['2026-06-04 11:32–11:33',2],['2026-07-24 16:00–16:01',2],['2026-09-24 15:45–15:48',4]]),'',
    '**ยังไม่ผ่าน strict gap-free/full-history validation:** มี 8 นาทีข้างต้น สาเหตุไม่ทราบ ไม่เติมราคา/แท่งสมมติ. ผลยอมรับเป็น bounded common-source native diagnostic; ไม่ได้พิสูจน์ว่าช่องว่างไม่มีผลทางเศรษฐกิจ. Current session metadata 00:00–23:00 ต่างจาก historical quote span ประมาณ 01:00–23:00; ไม่ระบุสาเหตุว่า DST. วันปิดเร็วบางวันไม่ยืนยันว่า holiday จากข้อมูลนี้.','',
    'May–September เป็น retrospective/exploratory ทั้งหมด; September เคยตรวจแล้ว ไม่ใช่ untouched holdout. MetaQuotes-Demo history/specs/costs ไม่ใช่การ replay production broker และไม่อธิบายสาเหตุครบทุก live loss.','',
    '**Measurement deviation — monthly DD เป็น estimate**','',
    'Protocol เดิมตั้งใจให้ callback DD เป็น lower bound. ผลจริง observed overall DD สูงกว่า native ทุกชุด จึงไม่รับรองข้ออ้างนั้น. เก็บ protocol เดิมเป็น frozen record; comparison JSON และตารางใช้ sampled estimate. สาเหตุ discrepancy ไม่ทราบ. Native overall equity DD เป็นค่าหลัก; monthly estimate ไม่ใช่ exact native DD หรือ proven lower bound.','',
    table(['ทุน / Policy','Native overall DD USD','Observed overall DD USD','Observed − native'],[
      [f"${r['deposit']:,.0f} / {labels[r['variant']]}",f"{r['native_equity_dd']:.2f}",f"{float(r['broker_specs']['observed_overall_equity_dd']):.2f}",f"{r['observed_overall_dd_minus_native']:+.2f}"] for r in runs]),'',
    table(['ทุน / Policy','เดือน','DD sampled USD / %','Net loss streak สูงสุดที่กำลังต่อเนื่อง'],[
      [f"${r['deposit']:,.0f} / {labels[r['variant']]}",month,f"{b['observed_equity_dd_sampled']:.2f} / {b['observed_equity_dd_pct_sampled']:.3f}%",b['max_ongoing_loss_streak']] for r in runs for month,b in r['monthly'].items()]),'',
    '**การตรวจและไฟล์หลัก**','',
    'Compile benchmark/probe: 0 errors, 0 warnings. Accounting tests: 8 cases รวม entry costs, partial exits, unsupported positions และ signal/deal join ข้ามนาที. Full-period original EX5 กับ benchmark baseline: 2,987 trades, net -$1,342.34, 11,948 matching Orders/Deals rows พร้อมราคา เวลา SL/TP และ breaker sequence. Native HTML timestamp parity ระดับวินาที; original EX5 ไม่มี millisecond export จึงไม่อ้าง exact millisecond parity.','',
    f"- [Comparison JSON]({link(BASE/'comparison.json')}) — authoritative results, position deals, monthly metrics, specs, hashes.",
    f"- [Full-period parity]({link(BASE/'parity_full.json')}) และ [minute data audit]({link(BASE/'market_quality_final.json')}).",
    f"- [Frozen protocol]({link(ROOT/'docs/V23_BACKTEST_PROTOCOL_20261004.md')}) และ [raw run directory]({link(BASE/'runs')}).",
    f"- [Benchmark source]({link(ROOT/'research/V23_BacktestBenchmark.mq5')}), [runner]({link(ROOT/'scripts/run_v23_backtest.ps1')}), [evaluator]({link(ROOT/'research/analyze_v23_backtest.py')}).",'',
    'EA production source SHA256 `C19A29A45925C21305D6B1A8FE4616B8AEEDF1A487B0D278EDAD0880409EDFB0`; EX5 `E5B725EC83945B9E2126B72978E02A2EFCA28EC33AD649E575B4F5E2F4021AC0`. ตรวจหลังงานแล้วตรงเดิม. ไม่ deploy และไม่แก้ VM/live configuration.','',
    'Review loop: coordinator gpt-6.1-sol xhigh, reviewers 2 ตัว gpt-6.1-sol medium; root รับ implementation เพราะระบบจำกัด 4 agent threads รวม root และไม่มีโมเดล 6.1-luna. ไม่มี worker Luna แยกที่สร้างสำเร็จ. ผ่านหลายรอบ predicate, attribution, data integrity, parity และ accounting review; strict full-coverage validation ยังไม่ผ่านตามข้อจำกัดข้างต้น.','',
    'ขั้นถัดไปที่ผลรองรับ: ซ่อม execution/report ตาม audit ต่อได้ แต่ไม่ถือว่าแก้ expectancy. การกลับ sign หรือ closeback เพียงเงื่อนไขเดียวไม่พอในชุดนี้; สัญญาณ/บริบทตลาดและต้นทุนต้องพิสูจน์ใหม่บน broker history ที่ตรง production และช่วงใหม่ที่ยังไม่ใช้เลือกกฎ.'])
(ROOT/'docs/V23_BACKTEST_5M_20261004.md').write_text('\n'.join(out)+'\n',encoding='utf-8')
print('Wrote reviewed report and closed-trade balance chart.')
