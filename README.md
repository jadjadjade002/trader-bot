# QuantumTitan Apex — Institutional MT5 Quantitative Trading System

ระบบเทรดอัตโนมัติ MetaTrader 5 (MQL5) มาตรฐานกองทุน Quantitative ระดับสถาบันสำหรับสินทรัพย์ XAUUSD (Gold) และคู่สกุลเงินหลัก ออกแบบสถาปัตยกรรม Multi-Agent แบบกระจายศูนย์ ผสานการมองภาพรวมตลาดแบบ Discretionary Prop-Trader (Smart Money Concepts, 50% Equilibrium Zone, Liquidity Sweeps, Fair Value Gaps, Daily Bias, Session Killzones), Alpha Confluence Scoring, ATR Geometric Grid, 3Commas Trailing Take Profit และระบบควบคุมความเสี่ยง High-Water Mark Drawdown

---

## 1. ข้อมูลเวอร์ชันล่าสุด (Version 14.00 Apex — Institutional Macro Brain)

QuantumTitan v14.00 Apex ได้รับการยกระดับครั้งประวัติศาสตร์ โดยติดตั้ง Institutional Macro Brain เพื่อจำลองกระบวนการตัดสินใจและมุมมองภาพรวมตลาดแบบเทรดเดอร์สถาบันมืออาชีพ (Discretionary Prop Trader) ร่วมกับระบบ Auto-Adaptive Timeframe Profile Engine บอทจะทำการวิเคราะห์โครงสร้างตลาดแบบ Top-Down และบังคับใช้กฎเหล็กด้าน Valuation อย่างเข้มงวด

### คุณสมบัติระดับสถาบันที่เพิ่มเข้ามาใน Version 14.00 Apex:

1. Institutional Equilibrium & Valuation Zone (The 50% Rule):
   - แบ่งโครงสร้างราคารอบสวิงหลักออกเป็น 3 โซน: Discount Zone (<48%), Equilibrium Zone (48% - 52%), และ Premium Zone (>52%)
   - บังคับใช้กฎเหล็กของสถาบัน (The Golden Rule): ห้ามซื้อในโซนแพง (Strictly 0 BUY Score in Premium) และห้ามขายในโซนถูก (Strictly 0 SELL Score in Discount) ขจัดปัญหาการไล่ราคาที่ปลายยอดหรือขายซ้ำที่ก้นเหวอย่างเด็ดขาด

2. Macro Liquidity Sweep Engine (PDH / PDL & Swing Purges):
   - ตรวจจับพฤติกรรม Turtle Soup ของราคาทองคำ โดยสแกนการกวาดสภาพคล่องเหนือจุดสูงสุดของวันก่อนหน้า (Previous Day High - PDH) หรือใต้จุดต่ำสุดของวันก่อนหน้า (Previous Day Low - PDL)
   - หากราคาพุ่งทะลุจุดสภาพคล่องแต่แท่งเทียนถัดมากลับมาปิดภายในกรอบ ระบบจะนับเป็นสัญญาณการล่อซื้อ/ล่อขายของสถาบัน (Stop-Run Reversal) และให้คะแนน Confluence สูงสุด

3. Fair Value Gap (FVG) & Imbalance Mitigation:
   - สแกนหาช่องว่างราคาที่เกิดจากการเคลื่อนที่อย่างรุนแรงแบบ 3 แท่งเทียน (3-Bar Displacement Imbalance)
   - ตรวจสอบการย่อตัวกลับมาทดสอบ (Mitigation / Rebalance) เพื่อเข้าออเดอร์ในจุดที่มีความได้เปรียบทางต้นทุนสูงสุด

4. Top-Down Daily Bias (D1 Macro Context):
   - วิเคราะห์ทิศทางกรอบเวลาวัน (D1) เปรียบเทียบราคาปัจจุบันกับ Daily Open และ Previous Close
   - กำหนดทิศทางการขยายตัวของแท่งวัน: Bullish Expansion, Bearish Expansion, หรือ Consolidation เพื่อให้บอทมองเห็นทิศทางลมของตลาดใหญ่ก่อนตัดสินใจ

5. Time & Price Session Killzones:
   - บูรณาการมิติของเวลา (Time & Price) ตามหลักการสถาบันระดับสากล:
     - London Killzone (07:00 - 11:00 Server Time): ช่วงเวลาที่สร้าง High/Low สำคัญของฝั่งยุโรป
     - New York Killzone (12:00 - 17:00 Server Time): ช่วงเวลาที่มีสภาพคล่องและความผันผวนสูงสุด
     - Asian / Off-Hours: ช่วงเวลาสภาพคล่องต่ำ ระบบจะระงับการให้คะแนนพิเศษ

6. Rebalanced 100-Point Institutional Confluence Scoring:
   - Higher Timeframe Trend Bias (EMA 20/50/200): สูงสุด 25 คะแนน
   - Institutional Valuation Zone (Discount / Premium): สูงสุด 20 คะแนน
   - Liquidity Sweeps & SMC Structure: สูงสุด 20 คะแนน
   - Fair Value Gap & Squeeze Momentum: สูงสุด 15 คะแนน
   - Multi-Timeframe RSI Volatility: สูงสุด 10 คะแนน
   - Session Killzone Confluence: สูงสุด 10 คะแนน
   - เกณฑ์ผ่านการอนุมัติ: 75/100 คะแนนขึ้นไป พร้อมเงื่อนไขสอดคล้องกับ Valuation Zone

7. Dual-ATR Dynamic Sizing & Timeframe Profiles:
   - M1 Ultra Scalper: ATR M1 + Noise Buffer (.50), TP ~.00 - .50, BE +0.30R, Trail +0.70R, Grid Step 1.5 ATR, Magic 991401
   - M5 Fast Intraday: ATR M5 + Noise Buffer (.50), TP ~.50 - .00, BE +0.35R, Trail +0.75R, Grid Step 1.2 ATR, Magic 991405
   - M15 Intraday Swing: ATR M15 + Noise Buffer (.50), TP ~.00 - .00, BE +0.35R, Trail +0.75R, Grid Step 1.1 ATR, Magic 991415
   - H1 Macro Trend: ATR H1 + Noise Buffer (.00), TP ~.00 - .00, BE +0.35R, Trail +0.75R, Grid Step 1.0 ATR, Magic 991460

---

## 2. โครงสร้างสถาปัตยกรรมระบบ (Core Modules)

ระบบแบ่งออกเป็น 5 โมดูลหลักที่ทำงานสอดประสานกันแบบ Decoupled:

### Module 1: Institutional Macro Brain & Alpha Scoring (Include/QuantumTitan/AlphaScoring.mqh)
- วิเคราะห์สภาวะตลาด 4 รูปแบบ: Trend Bull, Trend Bear, Chop Range, Volatility Shock ผ่าน ADX(14) และ Dynamic ATR
- คำนวณ Discount/Premium Zone, Macro Liquidity Sweeps, FVGs, Daily Bias และ Session Killzones แบบ Real-time
- คำนวณคะแนน Confluence รวม 100 จุด โดยห้าม BUY ในโซน Premium และห้าม SELL ในโซน Discount

### Module 2: Dynamic Trailing & Reversal Safety (Include/QuantumTitan/TrailingSafety.mqh)
- 3Commas Trailing Take Profit (TTP): ระบบ Trailing แบบปรับตัวตามความผันผวน ATR ล็อกกำไรตั้งแต่ 0.70R - 0.75R
- Early Breakeven Protection: เลื่อนจุดตัดขาดทุนมาบังหน้าทุนทันทีเมื่อกำไรแตะ 0.30R - 0.35R
- Trailing Buy Reversal Engine: ตรวจจับจังหวะการกลับตัวของราคาหลังจากเกิดการย่อตัวลึก เพื่อเข้าคำสั่งถัวเฉลี่ยในจุดที่ได้เปรียบ

### Module 3: ATR Geometric Grid & Dynamic Rebalancer (Include/QuantumTitan/DynamicGrid.mqh)
- Geometric Sizing Matrix: ปรับขนาดล็อตแบบเรขาคณิตตามระยะความผันผวนของตลาด
- Dynamic Cash Reserve Guard: ตรวจสอบ Free Margin ขั้นต่ำ 60% หากต่ำกว่าเกณฑ์จะระงับการเปิดเลเยอร์กริดใหม่ทันที
- Basket Take Profit: รวมกลุ่มคำสั่งเพื่อปิดทำกำไรพร้อมกันทั้งชุดเมื่อราคาวิ่งถึงเป้าหมาย ATR

### Module 4: Institutional Risk Guardian & News Shield (Include/QuantumTitan/RiskGuardian.mqh)
- High-Water Mark (HWM) Drawdown Circuit Breaker: คำนวณเพดาน Drawdown สูงสุดประจำวัน หากแตะ 8.0% จากจุดสูงสุดจะล็อกการเข้าออเดอร์ใหม่ทันที
- Hard Equity Floor: กำหนดจุดตัดขาดทุนฉุกเฉินระดับบัญชี หาก Equity ต่ำกว่าเพดานขั้นต่ำจะปิดทุกสถานะทันที
- MQL5 Native Economic News Engine: ดึงข้อมูลปฏิทินข่าวสารเศรษฐกิจความสำคัญสูง (High-Impact) แบบ Real-time หยุดพักการเทรด 30 นาทีก่อนและหลังข่าว
- Session Rollover & Weekend Protection: หยุดพักการเทรดช่วงเปลี่ยนถ่ายสภาพคล่องข้ามคืน (23:55 - 00:05) และจำกัดความเสี่ยงก่อนปิดสัปดาห์

### Module 5: Real-Time Visual Matrix HUD & Telemetry (Include/QuantumTitan/TelemetryHUD.mqh)
- On-Chart TradingView Dark Matrix Dashboard: แสดงข้อมูลสถานะบัญชี, ข่าวสาร, สเปรด, สภาวะตลาด, Macro Zone %, Daily Bias, Session Killzone, Alpha Score, และสถานะพอร์ต
- Throttled GUI Rendering: ควบคุมอัตราการวาดหน้าจอไม่เกิน 1 ครั้งต่อวินาที ป้องกันปัญหา Event Queue Overflow ใน MetaTrader 5
- Clean Institutional Typography: ใช้สัญลักษณ์ข้อความมาตรฐาน ปราศจากปัญหาฟอนต์เพี้ยนบนระบบจำลอง Linux/Wine

---

## 3. ประวัติการพัฒนาเวอร์ชัน (Version Evolution)

| เวอร์ชัน | วันที่อัปเดต | รายละเอียดการพัฒนา |
|---|---|---|
| v1.0 | กันยายน 2026 | ระบบเริ่มต้น ICT Liquidity Sweep, EMA 9/21, RSI 7, Break-Even และ Trailing Stop พื้นฐาน |
| v3.6 | กันยายน 2026 | High-Speed Scalper บน M1 พร้อมระบบ Cooldown Guard และ Dynamic ATR SL Buffer |
| v4.0 | กันยายน 2026 | ผสานแนวคิด TradingView: LazyBear Squeeze Momentum, LuxAlgo SMC Order Blocks, UT Bot Trailing |
| v5.0 | กันยายน 2026 | Fortified Edition: เพิ่ม H1 Trend Filter, ปรับปรุงตรรกะความปลอดภัย, จำกัด 15 ไม้/วัน, Losing Streak Guard |
| v6.0 | กันยายน 2026 | Institutional Master Edition: ผสาน Native MQL5 News Calendar Engine, Hard Equity Floor, Session Lockout |
| v7.0 | กันยายน 2026 | Apex Edition: เพิ่มการวาด Order Block และลูกศรบนชาร์ตแบบ Real-time, ระบบแจ้งเตือน Push Notification |
| v8.0 | กันยายน 2026 | Titan Edition: โหมดทำงานต่อเนื่อง 24/7, ปรับความไว Break-even 0.4R, RSI Anti-Chop Guard |
| v9.0 | กันยายน 2026 | Singularity Architecture: สถาปัตยกรรมแยก 5 โมดูลอิสระ เหนือกว่าเกณฑ์มาตรฐาน Pionex, 3Commas, Cryptohopper |
| v10.0 | กันยายน 2026 | Adversarial Hardened: ผ่านการทดสอบ Stress Test จำลองวิกฤติตลาด 500 รูปแบบ, เพิ่มการบันทึกสถานะผ่าน GlobalVariables |
| v11.0 | กันยายน 2026 | Anti-Chop Confluence, ปรับ Breakeven 0.35R, ปรับปรุงแดชบอร์ด HUD สไตล์ TradingView Dark Slate |
| v12.0 | กันยายน 2026 | Multi-Timeframe Matrix: รองรับการรันพร้อมกันบน M1, M5, M15, H1, Adaptive HTF Confluence, ขยายเพดานพอร์ตโฟลิโอ |
| v13.0 | กันยายน 2026 | Institutional Macro Brain: ผสาน SMC 50% Equilibrium Zone, Liquidity Sweeps, FVGs, Daily Bias, Killzones, Auto-Adaptive Profiles |
| v14.0 | กันยายน 2026 | Apex Release: ติดตั้ง 8-Factor Institutional Confluence Matrix, Nestled OB, Hidden-Base Fibo, Stateful FVG, Multi-TF Isolation (M1/M5/M15/H1) เต็มรูปแบบ |

---

## 4. โครงสร้างไฟล์ในโปรเจกต์ (Project Structure)

`	ext
trader-bot/
├── QuantumTitan_v14_Apex.mq5          # ซอร์สโค้ดหลักเวอร์ชัน 14.00 Apex (Institutional Macro Brain)
├── QuantumTitan_v14_Apex.ex5          # ไฟล์ไบนารีที่ผ่านการคอมไพล์ 0 Errors, 0 Warnings
├── Include/
│   └── QuantumTitan/
│       ├── AlphaScoring.mqh          # โมดูล Macro Brain, SMC Valuation และ Confluence Scoring
│       ├── DynamicGrid.mqh           # โมดูลกริดเรขาคณิตและจัดการเงินทุนสำรอง
│       ├── RiskGuardian.mqh          # โมดูลควบคุมความเสี่ยง ปฏิทินข่าวสาร และลิมิตพอร์ต
│       ├── TelemetryHUD.mqh          # โมดูลแดชบอร์ดแสดงผลบนกราฟและการแจ้งเตือน
│       └── TrailingSafety.mqh        # โมดูล Trailing Take Profit และจุดกลับตัว
├── versions/                         # คลังเก็บซอร์สโค้ดและไบนารีย้อนหลังทุกเวอร์ชัน
├── scripts/
│   ├── compile.ps1                   # สคริปต์คอมไพล์ซอร์สโค้ดอัตโนมัติผ่าน MetaEditor
│   ├── deploy.ps1                    # สคริปต์ส่งไฟล์ขึ้นระบบ MT5 บนเครื่อง Local
│   ├── deploy_to_vm.py               # สคริปต์ส่งไฟล์และติดตั้งบน Cloud VM
│   ├── generate_4charts.py           # สคริปต์จัดและสร้างไฟล์โปรไฟล์ 4 กราฟ (M1, M5, M15, H1)
│   ├── restart_mt5_vm.sh             # สคริปต์รีสตาร์ต MT5 Terminal บนระบบ Linux/Wine
│   └── start_mt5.sh                  # สคริปต์บูตระบบแสดงผล Xvfb, VNC, noVNC และ MT5
└── docs/                             # รายงานการตรวจสอบระบบและบันทึกภาพการทำงาน
`

---

## 5. การติดตั้งและใช้งาน (Installation & Setup)

### การคอมไพล์บนเครื่อง Local (Windows):
1. ตรวจสอบว่าได้ติดตั้ง MetaTrader 5 เรียบร้อยแล้ว
2. รันคำสั่งคอมไพล์ผ่าน PowerShell:
   `powershell
   powershell -ExecutionPolicy Bypass -File scripts\compile.ps1 QuantumTitan_v14_Apex
   `
3. ตรวจสอบว่าผลลัพธ์การคอมไพล์แสดง Result: 0 errors, 0 warnings

### การติดตั้งลงบน MetaTrader 5:
1. นำไฟล์ QuantumTitan_v14_Apex.ex5 ไปวางในไดเรกทอรี:
   MQL5\Experts\ หรือ MQL5\Experts\Advisors2. นำโฟลเดอร์ Include\QuantumTitan ไปวางในไดเรกทอรี:
   MQL5\Include3. เปิดโปรแกรม MetaTrader 5
4. ลาก Expert Advisor ลงบนกราฟที่ต้องการ (แนะนำ XAUUSD บน Timeframe M1, M5, M15 หรือ H1)
5. ตรวจสอบให้แน่ใจว่าได้เปิดปุ่ม Algo Trading (เป็นไอคอนสีเขียว) บนแถบเครื่องมือของ MT5

---

## 6. สถาปัตยกรรมระบบคลาวด์ (Cloud VM Infrastructure)

ระบบรองรับการติดตั้งและรันตลอด 24 ชั่วโมงบนเซิร์ฟเวอร์คลาวด์:
- สภาพแวดล้อม: Ubuntu 24.04 LTS x86_64
- การจำลองระบบ: Wine 9.0 พร้อม Virtual Display (Xvfb :0 1280x1024)
- การควบคุมระยะไกล: VNC Server (x11vnc) และ Web Interface (noVNC) ผ่านพอร์ต 6080
- การจัดการหน้าต่าง: จัดแสดง 4 ไทม์เฟรมพร้อมกันในรูปแบบ 2x2 Grid ครอบคลุม M1, M5, M15 และ H1
