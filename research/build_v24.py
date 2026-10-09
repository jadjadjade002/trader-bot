"""Package the tested proposed/BE-off signal into a demo-only production EA."""
from hashlib import sha256
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = "C19A29A45925C21305D6B1A8FE4616B8AEEDF1A487B0D278EDAD0880409EDFB0"


def function(text, name):
    match = re.search(r"^(?:void|bool|int|double)\s+"+re.escape(name)+r"\([^\n]*\)\s*\{", text, re.M)
    if match is None:
        raise ValueError("Function declaration missing: "+name)
    start = match.start()
    left = text.index("{", start)
    depth = 1
    right = left
    while depth:
        right += 1
        depth += (text[right] == "{") - (text[right] == "}")
    return text[start:right+1]


def generate():
    raw = (ROOT / "AegisPredator_v23.mq5").read_bytes()
    if sha256(raw).hexdigest().upper() != EXPECTED:
        raise ValueError("V23 production baseline changed")
    source = raw.decode("utf-8").replace("\r\n", "\n")
    extension = (ROOT / "research/v23_tuning_extension.mqh").read_text(encoding="utf-8")
    # Copy the actual tested signal verbatim. No optimized thresholds added.
    signal_functions = "\n\n".join(function(extension, name) for name in
                        ("ReleaseExperiment", "ReadClosed", "ProposedSignal"))
    control = (ROOT / "research/v24_demo_runtime.mqh").read_text(encoding="utf-8")
    source = source.replace("AegisPredator_v23.mq5", "AegisPredator_v24.mq5")
    source = source.replace('"23.00"', '"24.00"')
    source = source.replace('"Aegis Predator V23: Institutional False Breakout Liquidity Engine on XAUUSD M1."',
                            '"V24 demo research: closed M5 trend, M1 pullback/reclaim, TP2R, BE off. Historical net remains negative."')
    source = source.replace("Aegis Predator V23 INITIALIZED.", "Aegis Predator V24 INITIALIZED.")
    # The breaker body remains byte-for-byte identical to V23 after newline normalization.
    for old, new in (
        ('input bool     InpFadeBreakouts    = true;', 'input bool     InpFadeBreakouts    = false;'),
        ('ulong          lastBreakerDealTicket = 0;', 'ulong          lastBreakerDealTicket = 0;\n\n'+control),
        ('   // Safety: Ensure demo or authorized account',
         '   if(AccountInfoInteger(ACCOUNT_TRADE_MODE)!=ACCOUNT_TRADE_MODE_DEMO)\n'
         '   { Print("V24 BLOCKED: demo accounts only"); return INIT_FAILED; }\n'
         '   if(_Symbol!="XAUUSD" || _Period!=PERIOD_M1 || InpFadeBreakouts)\n'
         '   { Print("V24 BLOCKED: requires XAUUSD M1, FadeBreakouts=false"); return INIT_PARAMETERS_INCORRECT; }\n'
         '   if(InpATRPeriod<1 || InpDonchianPeriod<1 || InpStopLossATRMul<=0 || InpTakeProfitRRMul<=0\n'
         '      || InpMinSLPoints<1 || InpMaxHoldBars<1 || InpLotSize<=0\n'
         '      || InpMaxConsecutiveLosses<1 || InpCooldownMinutes<1) return INIT_PARAMETERS_INCORRECT;\n'
         '   // Safety: Ensure demo or authorized account'),
        ('   // Apply Charcoal / Teal & Coral Terminal Theme',
         '   if(!InitV24Signal())\n'
         '   { ReleaseExperiment(); Print("V24 BLOCKED: indicator initialization failed"); return INIT_FAILED; }\n'
         '   if(!EventSetTimer(300))\n'
         '   { ReleaseExperiment(); Print("V24 BLOCKED: heartbeat initialization failed"); return INIT_FAILED; }\n'
         '   V24Status("INITIALIZED_WAIT_NEXT_BAR");\n'
         '   LogV24Health();\n'
         '   // Apply Charcoal / Teal & Coral Terminal Theme'),
        ('void OnDeinit(const int reason)\n{',
         'void OnDeinit(const int reason)\n{\n   EventKillTimer();\n   ReleaseExperiment();\n   Comment("");'),
        ('   if(HasOpenPosition())\n      return;',
         '   if(HasOpenPosition())\n      { V24Status("MANAGING_POSITION"); return; }'),
        ('   if(IsCircuitBreakerActive())\n      return;',
         '   if(IsCircuitBreakerActive())\n      { V24Status("CIRCUIT_BREAKER_PAUSE"); return; }'),
        ('   if(signal == 0)\n      return;',
         '   signal=ProposedSignal(atr);\n   if(signal == 0)\n      { V24Status("WAIT_TREND_PULLBACK_COST_FILTER"); return; }\n'
         '   V24Status(signal==1 ? "BUY_CANDIDATE" : "SELL_CANDIDATE");'),
        ('"AegisPredator V23 Buy"', '"AegisPredator V24 Buy"'),
        ('"AegisPredator V23 Sell"', '"AegisPredator V24 Sell"'),
    ):
        if source.count(old) != 1:
            raise ValueError("Expected one packaging replacement: "+old)
        source = source.replace(old, new, 1)
    # Only passive status changes after successful/failed order requests.
    source = source.replace('PrintFormat("BUY ORDER PLACED. Ticket=%I64u", trade.ResultOrder());',
        'LogV24Order("BUY");')
    source = source.replace('PrintFormat("SELL ORDER PLACED. Ticket=%I64u", trade.ResultOrder());',
        'LogV24Order("SELL");')
    source = source.replace('Print("Aegis Predator V23 deinitialized. Reason: ", reason);',
                            'Print("Aegis Predator V24 deinitialized. Reason: ", reason);')
    return source+"\n\n"+signal_functions+"\n"


if __name__ == "__main__":
    (ROOT / "AegisPredator_v24.mq5").write_text(generate(), encoding="utf-8")
    print("Generated AegisPredator_v24.mq5. Demo-only, BE disabled, unchanged breaker.")
