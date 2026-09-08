# QuantumTitan v16.00 Singularity — Complete Project Context & Architecture Documentation
> **สถาปัตยกรรมและเอกสารอธิบายระบบการทำงานทั้งหมดของระบบเทรดอัตโนมัติ QuantumTitan v16.00**  
> *วันที่อัปเดตล่าสุด: 8 กันยายน 2026 | เวอร์ชัน: v16.00 Singularity | สินทรัพย์หลัก: XAUUSD (Gold vs US Dollar)*

---

## 1. ภาพรวมโครงการ (Project Overview)

**QuantumTitan v16.00 Singularity** คือระบบ Expert Advisor (EA) เชิงปริมาณขั้นสถาบัน (Institutional Quantitative Expert Advisor) สำหรับแพลตฟอร์ม MetaTrader 5 (MQL5) พัฒนาขึ้นเพื่อเทรดทองคำ (**XAUUSD**) โดยเฉพาะ บนโครงสร้าง **Multi-Timeframe Matrix (5 ชาร์ตรันขนานกัน)** ผสานทฤษฎี Smart Money Concepts (SMC), Price Action ขั้นสูง, โมเดลวัดความผันผวนทางคณิตศาสตร์ (Volatility Squeeze & ATR), ปฏิทินข่าวเศรษฐกิจแบบ Native และระบบควบคุมความเสี่ยงระดับสถาบัน (Capital Preservation Guardian)

### เป้าหมายและปรัชญาหลัก (Core Philosophy):
1. **Capital Preservation First**: เน้นการรักษาเงินต้นเป็นอันดับสูงสุด ด้วยระบบ High-Water Mark Equity Drawdown และ Circuit Breaker ตัดขาดทุนฉุกเฉิน
2. **Strict Lot Size Control**: ล็อคขนาดการออกออเดอร์ไว้ที่ **0.01 lot ทุกไม้ ทุกไทม์เฟรม และทุกชั้นของ Grid** โดยไม่มีการเบิ้ล lot, ไม่ใช้ Martingale, ไม่เสี่ยงล้างพอร์ต
3. **Multi-Timeframe Symbiosis**: ทำงานร่วมกัน 5 หน้าจอพร้อมกัน เพื่อให้มีทั้งตัวดักสวิงภาพใหญ่ (H1, M15), ตัวเก็งกำไรในวัน (M5), ตัวเก็บรอบไวแบบสไนเปอร์ (M1 Apex) และตัวสแปมอัจฉริยะโมเมนตัมสูง (M1 Velocity)
4. **Zero-Error Engineering & Asynchronous Race Condition Immunity**: ออกแบบโค้ดระดับ Production ที่ป้องกันข้อผิดพลาดทางเทคนิคทั้งหมด เช่น การแก้ไข/ปิด Position ซ้อน, โหมด Filling ผิดพลาด, หรือหน่วยความจำตกค้างข้ามบัญชี

---

## 2. โครงสร้างไฟล์และสถาปัตยกรรมโค้ด (Codebase Structure)

```
d:\project\trader-bot\
├── QuantumTitan_v16_Apex.mq5          # Master EA สำหรับ M1, M5, M15, H1 (SMC & Multi-Timeframe)
├── QuantumTitan_v16_Velocity.mq5      # EA พิเศษสำหรับ M1 (Squeeze Momentum Rapid Scalper)
├── generate_5charts.py                # สคริปต์ Python ประกอบและจัด Layout 5 ชาร์ตแบบ Tiled อัตโนมัติ
├── PROJECT_CONTEXT_v16.md             # เอกสารอธิบายงานและบริบททั้งระบบ
│
└── Include\QuantumTitan\              # โมดูลระบบเชิงปริมาณระดับสถาบัน (Modular Framework)
    ├── AlphaScoring.mqh               # โมดูลคำนวณคะแนน SMC & PA (11 Sub-Modules, Equilibrium Gate)
    ├── TrailingSafety.mqh             # โมดูล Trailing Stop, Break-Even Lock, Anti-Noise Buffer
    ├── DynamicGrid.mqh                # โมดูล Geometric Averaging Basket (ล็อค 0.01 lot ถาวร)
    ├── RiskGuardian.mqh               # โมดูลควบคุมความเสี่ยง, Circuit Breaker, News Filter
    └── TelemetryHUD.mqh               # โมดูลหน้าจอ Matrix HUD และ Canvas วาดเส้นกราฟิกวิเคราะห์
```

---

## 3. สถาปัตยกรรมโมดูลเชิงปริมาณ (Quantitative Modules Deep-Dive)

### โมดูลที่ 1: Alpha Scoring Engine (`AlphaScoring.mqh`)
สมองกลประเมินคุณภาพของสัญญาณ (Signal Quality Evaluator) คำนวณคะแนนตั้งแต่ 0 ถึง 100 คะแนน โดยรวมปัจจัย 11 ประการ:
1. **HTF Confluence (20 pts)**: แนวโน้มโครงสร้างจาก Higher Timeframe (H1/H4) สอดคล้องกับทิศทางเข้า
2. **Equilibrium / Discount-Premium Gate (Strict 50% Rule)**:
   - สัญญาณ **BUY** จะเปิดได้ต่อเมื่อราคาอยู่ในโซน **Discount (< 50% ของกรอบราคา)** เท่านั้น
   - สัญญาณ **SELL** จะเปิดได้ต่อเมื่อราคาอยู่ในโซน **Premium (> 50% ของกรอบราคา)** เท่านั้น
3. **Dynamic Fair Value Gap (FVG) (15 pts)**: การตรวจจับ Imbalance 3 แท่งเทียนที่ยังไม่ถูกทดสอบ (Mitigated)
4. **Liquidity Sweeps (15 pts)**: การกวาดสภาพคล่องเหนือ Swing High หรือใต้ Swing Low แล้วดีดกลับ
5. **Order Block (OB) Validation (10 pts)**: โซนการสะสมของสถาบันก่อนเกิด Displacement
6. **Institutional Displacement (10 pts)**: แท่งเทียนโมเมนตัมขนาดใหญ่ที่มีเนื้อเทียนกลืนกินตลาด (> 1.5 เท่าของแท่งปกติ)
7. **RSI Dynamic Exhaustion (10 pts)**: สภาวะหมดแรงของราคา Oversold (< 30) หรือ Overbought (> 70)
8. **Squeeze Momentum Indicator (John Carter)**: การบีบตัวของ Bollinger Bands ภายใน Keltner Channel เพื่อดักการระเบิดของราคา
9. **EMA Structural Trend Matrix**: การเรียงตัวของ EMA 14, EMA 50, และ EMA 200
10. **Volume Microstructure Expansion**: ปริมาณ Tick Volume สูงกว่าค่าเฉลี่ย 20 แท่ง
11. **Institutional Killzone Filter**: กรองช่วงเวลา New York Session, London Session และหลีกเลี่ยงช่วงตลาดซบเซา (Off-Hours)
*เกณฑ์การเปิดไม้*: ต้องได้คะแนนขั้นต่ำ $\ge 75/100$ คะแนน และต้องผ่านเงื่อนไข Equilibrium Gate 100%

### โมดูลที่ 2: Trailing Safety & Breakeven Lock (`TrailingSafety.mqh`)
* **Break-Even Early Lock**: เมื่อราคาวิ่งบวกไปถึง `0.30R - 0.35R` ระบบจะเลื่อน Stop Loss มาล็อคหน้าทุนทันที (+10 ถึง +25 points) เพื่อปิดความเสี่ยงให้กลายเป็น "Risk-Free Trade"
* **Adaptive Trailing Stop**: เมื่อราคาวิ่งต่อเนื่องเกิน `0.70R - 0.80R` ระบบจะเปิด Trailing Stop ตามระดับความผันผวนของ ATR (Trailing Step = 0.45 ATR) เพื่อรันเทรนด์ให้ได้กำไรสูงสุด
* **Anti-Noise Pip Buffer**: เพิ่มระยะกันชนตาม Timeframe เพื่อป้องกันไม่ให้สัญญาณรบกวน (Noise) หรือ Spread ของโบรกเกอร์มาเกี่ยว SL:
  - M1: กันชน 320 points ($3.2)
  - M5: กันชน 450 points ($4.5)
  - M15: กันชน 650 points ($6.5)
  - H1: กันชน 1,200 points ($12.0)
* **Race-Condition Immunity**: ใช้ `PositionSelectByTicket()` ตรวจสอบว่าออเดอร์ยังมีอยู่จริงในตลาด ก่อนสั่ง `PositionModify` หรือ `PositionClose` ทุกครั้ง ขจัดข้อผิดพลาด `[Position closed]` หรือ `[Position doesn't exist]` 100%

### โมดูลที่ 3: Geometric Dynamic Grid (`DynamicGrid.mqh`)
* **โครงสร้างการแก้ไม้**: ในกรณีที่ราคาเกิดการย่อตัวสวนทาง จะเปิดไม้เสริมแบบ Grid เพื่อดึงราคาเฉลี่ย (Average Entry)
* **การล็อค Lot Size**: บังคับ **0.01 lot ทุกไม้** ห้ามเพิ่มขนาดไม้เด็ดขาด
* **ระยะห่างตามความผันผวน (ATR Grid Spacing)**: ไม้ถัดไปจะเปิดก็ต่อเมื่อราคาวิ่งห่างจากไม้เดิมอย่างน้อย `1.0 - 1.3 ATR` (ป้องกันการเปิดไม้ถี่เกินไปในช่วงตลาดกระชาก)
* **จำกัดจำนวนไม้สูงสุด**: ไม่เกิน 4 ไม้ต่อรอบ (Max Orders = 4)
* **Cash Buffer & Margin Guard**: ตรวจสอบ Free Margin ต้องไม่ต่ำกว่า 60.0% เสมอ หาก Margin เหลือน้อยจะระงับการเปิดไม้ Grid ทันที

### โมดูลที่ 4: Risk Guardian Institutional Protocols (`RiskGuardian.mqh`)
* **High-Water Mark (HWM) Equity Tracking**: บันทึกจุดสูงสุดของ Equity ตลอดทั้งวันแบบ Real-time
* **Daily Drawdown Soft Circuit Breaker (8.0%)**:
  - หาก Equity ย่อตัวลงแตะ 8.0% จากจุดสูงสุดของวัน (HWM) ระบบจะล็อกการเปิดรอบใหม่ (New Cycle) ทันทีตลอดวันที่เหลือ
  - อนุญาตให้จัดการเฉพาะไม้ที่ค้างอยู่ (Manage/Exit Grid) เพื่อให้พอร์ตกลับมาสู่จุดปลอดภัย
* **Hard Equity Floor ($30.00)**: เส้นตายตัดขาดทุนฉุกเฉิน หากพอร์ตลดลงแตะระดับ $30.00 ระบบจะสั่ง Emergency Close ปิดทุกออเดอร์ทันทีเพื่อปกป้องเงินทุนส่วนที่เหลือ
* **Consecutive Loss Streak Protection**: หากแพ้ติดกัน 3 ไม้ จะพักการเทรดเป็นเวลา 60 นาที
* **Native MQL5 Economic Calendar News Filter**: ดึงข้อมูลข่าวเศรษฐกิจความสำคัญสูง (High Impact เช่น NFP, CPI, FOMC, Fed Chair Speech) แบบเรียลไทม์ผ่าน API `CalendarValueHistory()` พักการเข้าไม้ล่วงหน้า 30 นาทีก่อนข่าวออก และ 30 นาทีหลังข่าวออก
* **Microstructure Spread Surge Filter**: ตรวจจับความกว้างของ Spread หาก Spread พุ่งเกิน 60 points (ตลาดขาดสภาพคล่อง) จะระงับการเทรดทันที
* **Midnight Swap Rollover Blackout**: ระงับการเปิดไม้ช่วง 23:55 - 00:05 ตามเวลาเซิร์ฟเวอร์ เพื่อหลีกเลี่ยงการถ่าง Spread และค่า Swap

### โมดูลที่ 5: Telemetry Matrix HUD & Canvas (`TelemetryHUD.mqh`)
* แสดงแดชบอร์ดล้ำสมัยบนชาร์ตแบบ Real-time:
  - Account Mode & Current Balance / Equity
  - News Calendar Impact Status
  - Spread Points Real-time
  - HTF Trend Bias & Structural Direction
  - Macro Zone (Equilibrium / Discount / Premium)
  - Session Tracker (London / New York Killzone)
  - Alpha Score (Buy vs Sell Breakdown)
  - Active Basket & Floating PnL
  - Circuit Breaker State
* **On-Chart Technical Lines**: วาดเส้นแนวรับ-แนวต้าน, กรอบ Fair Value Gap (FVG), เส้น Equilibrium (50%), และระดับราคาสำคัญลงบนกราฟโดยอัตโนมัติ

---

## 4. ตาราง Multi-Timeframe Matrix (5 ชาร์ตทำงานคู่ขนาน)

การจัดวางชาร์ตถูกกำหนดและสร้างขึ้นผ่าน `generate_5charts.py` ในรูปแบบ Tiled Layout แบ่งเป็น 2 หน้าต่างใหญ่ฝั่งซ้าย และ 3 หน้าต่างฝั่งขวา:

| ชาร์ต | Timeframe | กลยุทธ์ / EA | Magic Number | คุณสมบัติหลัก |
| :--- | :--- | :--- | :--- | :--- |
| **Chart 1** | **XAUUSD M1** | `QuantumTitan_v16_Apex` | `991601` | M1 Ultra Scalper (SMC + FVG + Sweep) เก็บกำไรเร็ว SL 320 pts, TP 1.35R |
| **Chart 2** | **XAUUSD M1** | `QuantumTitan_v16_Velocity` | `991601` | M1 Rapid Momentum (Squeeze Mom + EMA Pullback) Quick TP +180 pts ($1.80), BE +85 pts |
| **Chart 3** | **XAUUSD M5** | `QuantumTitan_v16_Apex` | `991605` | M5 Fast Intraday (HTF: H1) SL 450 pts, TP 1.25R, คุมรอบสวิงระยะสั้น |
| **Chart 4** | **XAUUSD M15** | `QuantumTitan_v16_Apex` | `991615` | M15 Intraday Swing (HTF: H1) SL 650 pts, TP 1.25R, คุมโครงสร้างรายวัน |
| **Chart 5** | **XAUUSD H1** | `QuantumTitan_v16_Apex` | `1007985` | H1 Macro Trend (HTF: H4) SL 1,200 pts, TP 1.25R, คุมทิศทางภาพใหญ่ของสถาบัน |

---

## 5. การแก้ไขบั๊กและพัฒนาความแข็งแกร่ง (System Hardening History)

### 1. การแก้ปัญหา Race Condition บน PositionModify / PositionClose
* **อาการเดิม**: ในสภาวะตลาดผันผวนเร็ว บอทมีการสั่ง Modify SL หรือ Close Position ซ้ำกัน ทำให้เกิด error `[Position closed]` หรือ `[Position doesn't exist]`
* **การแก้ไข**: ใส่ Wrapper `PositionSelectByTicket(ticket)` ตรวจสอบสถานะก่อนส่งคำสั่ง และเพิ่มการหน่วงเวลาตรวจสอบผลลัพธ์ ทำให้ไม่มี error ขึ้นใน Journal อีกต่อไป

### 2. การแก้ปัญหา GlobalVariable ข้ามบัญชี (Account Isolation Bug)
* **อาการเดิม**: เมื่อเปลี่ยนบัญชีใหม่จาก `5055578643` เป็น `112334471` บอทขึ้นสถานะ `PAUSED [CIRCUIT BREAKER: Daily DD 0.00% reached]` เนื่องจากตัวแปรระดับ Terminal จำค่า `QT_<magic>_<symbol>_CB` จากบัญชีเก่าที่เคยโดนหยุดการเทรด
* **การแก้ไข**: อัปเดตฟังก์ชันสร้างชื่อ GlobalVariable ให้ผูกกับ `AccountInfoInteger(ACCOUNT_LOGIN)` เสมอ:
  ```mql5
  long login = AccountInfoInteger(ACCOUNT_LOGIN);
  m_gvHwm = StringFormat("QT_%I64d_%I64u_%s_HWM", login, m_magic, safeSymbol);
  m_gvDay = StringFormat("QT_%I64d_%I64u_%s_DAY", login, m_magic, safeSymbol);
  m_gvCB  = StringFormat("QT_%I64d_%I64u_%s_CB",  login, m_magic, safeSymbol);
  ```
  ส่งผลให้แต่ละบัญชีแยก High-Water Mark และ Circuit Breaker อิสระจากกัน 100%

### 3. การรองรับ Dynamic Filling Mode Resolution
* **อาการเดิม**: โบรกเกอร์แต่ละรายหรือบัญชีแต่ละประเภทอาจรองรับเฉพาะ `ORDER_FILLING_FOK` หรือ `ORDER_FILLING_IOC` หรือ `ORDER_FILLING_RETURN` หากระบุผิดจะส่งคำสั่งไม่ผ่าน (Error 4756: Unsupported filling mode)
* **การแก้ไข**: เพิ่มฟังก์ชันอ่านค่า `SYMBOL_FILLING_MODE` จากเซิร์ฟเวอร์แบบ Dynamic และตั้งค่าโหมดที่โบรกเกอร์รองรับโดยอัตโนมัติก่อนส่งออเดอร์ทุกครั้ง

---

## 6. สภาพแวดล้อมระบบและการรันบน Cloud VPS (Deployment Stack)

* **Server OS**: Linux Ubuntu 24.04 LTS (IP: `161.118.255.178`)
* **Wine Environment**: Wine 9.0 (Windows 10 64-bit emulation)
* **Display Engine**: Headless X11 (Display `:0`)
* **MT5 Execution**: Portable Mode (`terminal64.exe /portable`)
* **Auto Chart Generator**: รัน `generate_5charts.py` เพื่อสร้างไฟล์ `.chr` สำหรับแต่ละชาร์ต และสร้าง `order.wnd` เพื่อคุมตำแหน่งหน้าต่างอัตโนมัติเมื่อเปิดโปรแกรม

---

## 7. ข้อมูลบัญชีจริงและการเชื่อมต่อ (Live Account Credentials)

* **ชื่อบัญชี**: `Jade Titan`
* **Account Login ID**: `112334471`
* **Broker / Server**: `MetaQuotes-Demo`
* **เงินทุนเริ่มต้น (Deposit)**: **$50.00 USD**
* **Leverage**: `1:500`
* **อีเมลที่ลงทะเบียน**: `jadesadaa002@gmail.com`
* **เบอร์โทรศัพท์**: `0909644528`
* **การเชื่อมต่อในมือถือ**: สามารถใช้แอป MetaTrader 5 สแกน QR Code หรือค้นหา Broker `MetaQuotes-Demo` แล้วกรอก Login ID `112334471`

---

## 8. ผลการทดสอบการเทรดสดล่าสุด (Live Verification Results)

ทันทีที่ปลดล็อคเข้าบัญชี `112334471`:
* **ยอดเงินเริ่มต้น**: $50.00 USD
* **ยอดเงินปัจจุบัน**: **$52.61 USD**
* **กำไรสุทธิ (Net Profit)**: **+$2.61 USD (+5.22%)**
* **จำนวนไม้ที่เทรดไป**: 4 ไม้
* **Win Rate**: **75.0%** (ชนะ 3 / แพ้ 1)
* **Lot Size ทุกไม้**: **0.01 lot** อย่างแม่นยำ
* **สถานะปัจจุบัน**: บอททั้ง 5 ชาร์ตทำงานประสานกันปกติและสแตนด์บายเฝ้าจับสัญญาณใหม่อย่างต่อเนื่อง 24 ชั่วโมง
