import os

CHARTS_DIR = '/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Profiles/Charts/Default'

TEMPLATE_V14 = """<chart>
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
InpMaxSpreadPoints=65.0
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

TEMPLATE_V15 = """<chart>
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
name=QuantumTitan_v15_Velocity
path=Experts\\QuantumTitan_v15_Velocity.ex5
expertmode=1
<inputs>
=== 1. ACCOUNT SECURITY & CAPITAL PRESERVATION ====
InpDemoOnly=true
InpMagicNumber=991501
InpMaxAccountLots=0.20
InpMaxSpreadPoints=65.0
InpMaxDailyLossPct=8.0
InpHardEquityFloor=30.0
InpMaxTradesPerDay=35
InpMaxLosingStreak=3
=== 2. MQL5 NATIVE ECONOMIC NEWS SHIELD ====
InpUseNewsFilter=true
InpNewsBufferMinsBefore=15
InpNewsBufferMinsAfter=15
=== 3. LAZYBEAR SQUEEZE MOMENTUM (TradingView Port) ====
InpBBLength=20
InpBBMult=2.000000
InpKCLength=20
InpKCMult=1.500000
=== 4. EMA TREND & RETEST (เทรดทองทำกำไรตลอดชีวิต PDF) ====
InpFastEmaPeriod=14
InpSlowEmaPeriod=50
InpWickRatioThreshold=0.250000
=== 5. M1 HIGH-WINRATE SCALP TARGETS (Quick TP) ====
InpBaseLot=0.010000
InpTakeProfitPoints=180.000000
InpStopLossPoints=260.000000
InpBreakevenTriggerPts=85.000000
InpBreakevenLockPts=15.000000
InpCooldownBars=1
=== 6. VISUAL MATRIX HUD ====
InpEnableHUD=true
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
    # Chart 1: M1 Apex — top-left
    {"name": "chart01.chr", "id": 5001001, "period_type": 0, "period_size": 1,
     "w_left": 0, "w_top": 0, "w_right": 960, "w_bottom": 540, "template": "v14"},
    # Chart 2: M1 Velocity (NEW) — bottom-left
    {"name": "chart02.chr", "id": 5001002, "period_type": 0, "period_size": 1,
     "w_left": 0, "w_top": 540, "w_right": 960, "w_bottom": 1080, "template": "v15"},
    # Chart 3: M5 Apex — top-right
    {"name": "chart03.chr", "id": 5001005, "period_type": 0, "period_size": 5,
     "w_left": 960, "w_top": 0, "w_right": 1920, "w_bottom": 360, "template": "v14"},
    # Chart 4: M15 Apex — mid-right
    {"name": "chart04.chr", "id": 5001015, "period_type": 0, "period_size": 15,
     "w_left": 960, "w_top": 360, "w_right": 1920, "w_bottom": 720, "template": "v14"},
    # Chart 5: H1 Apex — bottom-right
    {"name": "chart05.chr", "id": 5001060, "period_type": 1, "period_size": 1,
     "w_left": 960, "w_top": 720, "w_right": 1920, "w_bottom": 1080, "template": "v14"},
]

for c in charts:
    tmpl = TEMPLATE_V15 if c["template"] == "v15" else TEMPLATE_V14
    content = tmpl.format(**c)
    filepath = os.path.join(CHARTS_DIR, c["name"])
    with open(filepath, "w", encoding="utf-16le") as f:
        f.write("\ufeff" + content.replace("\n", "\r\n"))
    print(f"Generated {c['name']} (Template: {c['template']})")

order_content = "chart01.chr\r\nchart02.chr\r\nchart03.chr\r\nchart04.chr\r\nchart05.chr\r\n"
order_path = os.path.join(CHARTS_DIR, "order.wnd")
with open(order_path, "w", encoding="utf-16le") as f:
    f.write("\ufeff" + order_content)

print("Generated order.wnd with 5 charts (M1 Apex, M1 Velocity, M5, M15, H1) successfully!")
