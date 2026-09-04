import os

files = [
    r"C:\Users\USER\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\Advisors\QuantumSniper_v7_Apex.mq5",
    r"C:\Users\USER\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\Advisors\QuantumSniper_v6_Institutional.mq5",
    r"C:\Users\USER\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\Advisors\QuantumSniper_EA.mq5",
    r"D:\project\trader-bot\QuantumSniper_EA.mq5",
    r"D:\project\trader-bot\versions\QuantumSniper_v7_Apex.mq5"
]

target_text = '   if(InpUseHTFFilter && htfBias == 0)\n   {\n      g_lastSignalReason = "🚫 Choppy H1 Market - Standing By";\n      return;\n   }'
replace_text = '   // FIX: If H1 is neutral/ranging (htfBias == 0), ALLOW trade! Only block direct counter-trend (buy in bear, sell in bull).'

for p in files:
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            c = f.read()
        if target_text in c:
            c = c.replace(target_text, replace_text)
            with open(p, "w", encoding="utf-8") as f:
                f.write(c)
            print("Successfully updated:", p)
        else:
            print("Target not found in:", p)
