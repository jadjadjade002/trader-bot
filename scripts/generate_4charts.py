import os

CHARTS_DIR = '/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Profiles/Charts/Default'

CHART_TEMPLATE = """<chart>
id={id}
symbol=XAUUSD
description=Gold vs US Dollar
period_type={period_type}
period_size={period_size}
digits=2
tick_size=0.010000
scale_fix=0
scale_bar=0
scale=16
mode=1
fore=0
grid=0
volume=1
scroll=1
shift=1
shift_size=15.000000
fixed_pos=0.000000
ticker=1
ohlc=0
one_click=0
one_click_btn=1
bidline=1
askline=0
lastline=0
days=0
descriptions=0
tradelines=1
tradehistory=1
window_left={w_left}
window_top={w_top}
window_right={w_right}
window_bottom={w_bottom}
window_type=1
floating=0
floating_left=0
floating_top=0
floating_right=0
floating_bottom=0
floating_type=1
floating_toolbar=1
floating_tbstate=
background_color=2234131
foreground_color=12496805
barup_color=10135078
bardown_color=5264367
bullcandle_color=10135078
bearcandle_color=5264367
chartline_color=10135078
volumes_color=10135078
grid_color=3023388
bidline_color=10135078
askline_color=5264367
lastline_color=49152
stops_color=255
windows_total=1

<expert>
name=QuantumTitan_v14_Apex
path=Experts\\QuantumTitan_v14_Apex.ex5
expertmode=1
<inputs>
=== 1. ACCOUNT SECURITY & CAPITAL PRESERVATION ====
InpDemoOnly=true
InpMagicNumber=991400
InpAutoMagicByPeriod=true
InpMaxAccountLots=0.20
InpMaxSpreadPoints=45.0
InpMaxDailyLossPct=8.0
InpHardEquityFloor=30.0
InpMaxTradesPerDay=16
InpMaxLosingStreak=3
=== 2. MQL5 NATIVE ECONOMIC NEWS SHIELD ====
InpUseNewsFilter=true
InpNewsBufferMinsBefore=30
InpNewsBufferMinsAfter=30
InpFilterUSDOnly=true
=== 3. MARKET REGIME & ALPHA SCORING (vs Cryptohopper) ====
InpScoreThreshold=75
InpADXTrendLevel=25
InpShockMultiplier=2.2
InpHTF=16385
=== 4. DYNAMIC TRAILING & SAFETY (vs 3Commas) ====
InpBreakEvenTriggerR=0.35
InpTrailingTriggerR=0.75
InpTrailingAtrMult=0.45
InpSafetyBouncePoints=35.0
=== 5. ATR GEOMETRIC GRID & CASH BUFFER (vs Pionex) ====
InpBaseLot=0.01
InpMaxGridOrdersPerSide=4
InpGridStepAtrMult=1.0
InpLotMultiplier=1.25
InpMinMarginReservePct=60.0
InpBasketTpAtrMult=0.8
=== 6. VISUAL MATRIX HUD & TELEMETRY ====
InpEnableHUD=true
InpSendPushAlerts=true
InpSendPopAlerts=false
</inputs>
</expert>

<window>
height=100.000000
objects=0

<indicator>
name=Main
path=
apply=1
show_data=1
scale_inherit=0
scale_line=0
scale_line_percent=50
scale_line_value=0.000000
scale_fix_min=0
scale_fix_min_val=0.000000
scale_fix_max=0
scale_fix_max_val=0.000000
expertmode=0
fixed_height=-1
</indicator>
</window>
</chart>
"""

charts = [
    # M1
    {"name": "chart01.chr", "id": 5001001, "period_type": 0, "period_size": 1,
     "w_left": 0, "w_top": 0, "w_right": 635, "w_bottom": 460},
    # M5
    {"name": "chart02.chr", "id": 5001005, "period_type": 0, "period_size": 5,
     "w_left": 635, "w_top": 0, "w_right": 1270, "w_bottom": 460},
    # M15
    {"name": "chart03.chr", "id": 5001015, "period_type": 0, "period_size": 15,
     "w_left": 0, "w_top": 460, "w_right": 635, "w_bottom": 920},
    # H1
    {"name": "chart04.chr", "id": 5001060, "period_type": 1, "period_size": 1,
     "w_left": 635, "w_top": 460, "w_right": 1270, "w_bottom": 920},
]

for c in charts:
    content = CHART_TEMPLATE.format(**c)
    filepath = os.path.join(CHARTS_DIR, c["name"])
    with open(filepath, 'w', encoding='utf-16le') as f:
        f.write('\ufeff' + content.replace('\n', '\r\n'))
    print(f"Generated {c['name']} (PeriodType: {c['period_type']}, PeriodSize: {c['period_size']})")

order_content = "chart01.chr\r\nchart02.chr\r\nchart03.chr\r\nchart04.chr\r\n"
order_path = os.path.join(CHARTS_DIR, "order.wnd")
with open(order_path, 'w', encoding='utf-16le') as f:
    f.write('\ufeff' + order_content)

print("Generated order.wnd with 4 charts (M1, M5, M15, H1) successfully!")
