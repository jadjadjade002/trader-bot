# QuantumTitan Singularity — Institutional MT5 Quantitative Trading System

ระบบเทรดอัตโนมัติ MetaTrader 5 (MQL5) มาตรฐานกองทุน Quantitative ระดับสถาบันสำหรับสินทรัพย์ XAUUSD (Gold) และคู่สกุลเงินหลัก ออกแบบสถาปัตยกรรม Multi-Agent แบบกระจายศูนย์ ผสานการวิเคราะห์สภาวะตลาด (Regime Detection), Alpha Confluence Scoring, ATR Geometric Grid, 3Commas Trailing Take Profit และระบบควบคุมความเสี่ยง High-Water Mark Drawdown

---

## 1. ข้อมูลเวอร์ชันล่าสุด (Version 12.00 Singularity)

QuantumTitan v12.00 Singularity รองรับการทำงานพร้อมกันหลายไทม์เฟรม (Multi-Timeframe Matrix) บนกราฟ M1, M5, M15 และ H1 อย่างเป็นอิสระ โดยมีระบบแยก Magic Number และคำนวณกรอบเวลาอ้างอิงระดับสถาบันแบบอัตโนมัติ

### คุณสมบัติหลักในเวอร์ชัน 12.00:
- Multi-Timeframe Magic Number Isolation: คำนวณ Magic Number แยกตาม Timeframe อัตโนมัติ (M1: 991201, M5: 991205, M15: 991215, H1: 1007585) เพื่อแยกคำสั่งซื้อขาย กริด และการตัดขาดทุนของแต่ละกราฟอย่างเด็ดขาด
- Adaptive Higher-Timeframe Confluence: ปรับหาเทรนด์ระดับสถาบันอัตโนมัติ สำหรับกราฟ M1, M5, M15 จะอ้างอิงเทรนด์ H1 ส่วนกราฟ H1 จะยกระดับอ้างอิงเทรนด์ H4
- Portfolio Exposure Protection: ปรับเพดานสัดส่วนขนาดล็อตภาพรวมพอร์ตโฟลิโอ (InpMaxAccountLots = 0.20) เพื่อรองรับการเปิดคำสั่งพร้อมกัน 4 ไทม์เฟรม
- OnTradeTransaction Deal Match: ปรับปรุงการตรวจสอบ Deal Magic ให้ตรงกับ Instance Magic เพื่อบันทึกประวัติกำไรขาดทุนและการรีเซ็ต Risk Cache ทันที
- Microstructure Spread Surge Calibration: ปรับเกณฑ์การตรวจจับ Spread Surge ให้สอดคล้องกับพฤติกรรมสเปรดปกติของทองคำ ป้องกันการล็อกการเทรดโดยไม่จำเป็น

---

## 2. โครงสร้างสถาปัตยกรรมระบบ (Core Modules)

ระบบแบ่งออกเป็น 5 โมดูลหลักที่ทำงานสอดประสานกัน:

### Module 1: Market Regime & Alpha Confluence Scoring (Include/QuantumTitan/AlphaScoring.mqh)
- Market Regime Detection: จำแนกสภาวะตลาด 4 รูปแบบ (Trend Bull, Trend Bear, Chop Range, Volatility Shock) ผ่าน ADX(14) และ Dynamic ATR
- 100-Point Confluence Scoring:
  - Higher Timeframe Trend Bias (30 คะแนน): EMA 20, 50, 200 บนกรอบเวลาใหญ่
  - LuxAlgo SMC Liquidity Sweep & Order Block (25 คะแนน): สแกนการกวาดสภาพคล่องและการดีดตัวของแท่งเทียนสถาบัน
  - LazyBear Squeeze Momentum (25 คะแนน): ตรวจจับการบีบอัดและระเบิดตัวของ Bollinger Bands ภายใน Keltner Channels
  - Multi-Timeframe RSI Volatility (20 คะแนน): กรองจุดกลับตัวและพื้นที่ Overbought/Oversold
- Strict Trend-Gatekeeper: กำหนดเงื่อนไขคะแนนขั้นต่ำ 75/100 และต้องมีทิศทางสอดคล้องกับเทรนด์ใหญ่เท่านั้นจึงจะอนุญาตให้เปิดวงจรใหม่

### Module 2: Dynamic Trailing & Reversal Safety (Include/QuantumTitan/TrailingSafety.mqh)
- 3Commas Trailing Take Profit (TTP): ระบบ Trailing แบบปรับตัวตามความผันผวน ATR ล็อกกำไรตั้งแต่ 0.75R
- Early Breakeven Protection: เลื่อนจุดตัดขาดทุนมาบังหน้าทุนทันทีเมื่อกำไรแตะ 0.35R
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
- On-Chart TradingView Dark Matrix Dashboard: แสดงข้อมูลสถานะบัญชี, โหมดการเทรด, สเปรด, สภาวะตลาด, คะแนน Alpha Score, และคำสั่งที่เปิดอยู่บนหน้าจอ
- Throttled GUI Rendering: ควบคุมอัตราการวาดหน้าจอไม่เกิน 1 ครั้งต่อวินาที เพื่อป้องกันปัญหา Event Queue Overflow ใน MetaTrader 5

---

## 3. ประวัติการพัฒนาเวอร์ชัน (Version Evolution)

| เวอร์ชัน | วันที่อัปเดต | รายละเอียดการพัฒนา |
|---|---|---|
| **v1.0** | กันยายน 2026 | ระบบเริ่มต้น ICT Liquidity Sweep, EMA 9/21, RSI 7, Break-Even และ Trailing Stop พื้นฐาน |
| **v3.6** | กันยายน 2026 | High-Speed Scalper บน M1 พร้อมระบบ Cooldown Guard และ Dynamic ATR SL Buffer |
| **v4.0** | กันยายน 2026 | ผสานแนวคิด TradingView: LazyBear Squeeze Momentum, LuxAlgo SMC Order Blocks, UT Bot Trailing |
| **v5.0** | กันยายน 2026 | Fortified Edition: เพิ่ม H1 Trend Filter, ปรับปรุงตรรกะความปลอดภัย, จำกัด 15 ไม้/วัน, Losing Streak Guard |
| **v6.0** | กันยายน 2026 | Institutional Master Edition: ผสาน Native MQL5 News Calendar Engine, Hard Equity Floor, Session Lockout |
| **v7.0** | กันยายน 2026 | Apex Edition: เพิ่มการวาด Order Block และลูกศรบนชาร์ตแบบ Real-time, ระบบแจ้งเตือน Push Notification |
| **v8.0** | กันยายน 2026 | Titan Edition: โหมดทำงานต่อเนื่อง 24/7, ปรับความไว Break-even 0.4R, RSI Anti-Chop Guard |
| **v9.0** | กันยายน 2026 | Singularity Architecture: สถาปัตยกรรมแยก 5 โมดูลอิสระ เหนือกว่าเกณฑ์มาตรฐาน Pionex, 3Commas, Cryptohopper |
| **v10.0** | กันยายน 2026 | Adversarial Hardened: ผ่านการทดสอบ Stress Test จำลองวิกฤติตลาด 500 รูปแบบ, เพิ่มการบันทึกสถานะผ่าน GlobalVariables |
| **v11.0** | กันยายน 2026 | Anti-Chop Confluence, ปรับ Breakeven 0.35R, ปรับปรุงแดชบอร์ด HUD สไตล์ TradingView Dark Slate |
| **v12.0** | กันยายน 2026 | Multi-Timeframe Matrix: รองรับการรันพร้อมกันบน M1, M5, M15, H1, Adaptive HTF Confluence, ขยายเพดานพอร์ตโฟลิโอ |

---

## 4. โครงสร้างไฟล์ในโปรเจกต์ (Project Structure)

```text
trader-bot/
├── QuantumTitan_v12_Singularity.mq5   # ซอร์สโค้ดหลักเวอร์ชัน 12.00
├── QuantumTitan_v12_Singularity.ex5   # ไฟล์ไบนารีที่ผ่านการคอมไพล์ 0 Errors
├── Include/
│   └── QuantumTitan/
│       ├── AlphaScoring.mqh          # โมดูลวิเคราะห์สภาวะตลาดและคะแนนสัญญาณ
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
│   ├── restart_mt5.sh                # สคริปต์รีสตาร์ต MT5 Terminal บนระบบ Linux/Wine
│   └── start_mt5.sh                  # สคริปต์บูตระบบแสดงผล Xvfb, VNC, noVNC และ MT5
└── docs/                             # รายงานการตรวจสอบระบบและบันทึกภาพการทำงาน
```

---

## 5. การติดตั้งและใช้งาน (Installation & Setup)

### การคอมไพล์บนเครื่อง Local (Windows):
1. ตรวจสอบว่าได้ติดตั้ง MetaTrader 5 เรียบร้อยแล้ว
2. รันคำสั่งคอมไพล์ผ่าน PowerShell:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\compile.ps1 QuantumTitan_v12_Singularity
   ```
3. ตรวจสอบว่าผลลัพธ์การคอมไพล์แสดง `Result: 0 errors, 0 warnings`

### การติดตั้งลงบน MetaTrader 5:
1. นำไฟล์ `QuantumTitan_v12_Singularity.ex5` ไปวางในไดเรกทอรี:
   `MQL5\Experts\` หรือ `MQL5\Experts\Advisors\`
2. นำโฟลเดอร์ `Include\QuantumTitan` ไปวางในไดเรกทอรี:
   `MQL5\Include\`
3. เปิดโปรแกรม MetaTrader 5
4. ลาก Expert Advisor ลงบนกราฟที่ต้องการ (แนะนำ XAUUSD บน Timeframe M1, M5, M15 หรือ H1)
5. ตรวจสอบให้แน่ใจว่าได้เปิดปุ่ม **Algo Trading** (เป็นไอคอนสีเขียว) บนแถบเครื่องมือของ MT5

---

## 6. สถาปัตยกรรมระบบคลาวด์ (Cloud VM Infrastructure)

ระบบรองรับการติดตั้งและรันตลอด 24 ชั่วโมงบนเซิร์ฟเวอร์คลาวด์:
- สภาพแวดล้อม: Ubuntu 24.04 LTS x86_64
- การจำลองระบบ: Wine 9.0 พร้อม Virtual Display (Xvfb :0 1280x1024)
- การควบคุมระยะไกล: VNC Server (x11vnc) และ Web Interface (noVNC) ผ่านพอร์ต 6080
- การจัดการหน้าต่าง: จัดแสดง 4 ไทม์เฟรมพร้อมกันในรูปแบบ 2x2 Grid ครอบคลุม M1, M5, M15 และ H1
