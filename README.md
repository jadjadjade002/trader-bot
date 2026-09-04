# ⚡ QuantumSniper EA — Institutional MT5 Trading Bot

หุ่นยนต์เทรดอัตโนมัติ MetaTrader 5 (MQL5) สำหรับคู่เงิน XAUUSD (Gold) และ EURUSD ที่ผสานแนวคิด Smart Money Concepts (SMC), LazyBear Squeeze Momentum และ Multi-Timeframe Trend Following

---

## 📌 Versions Overview & Branch Structure

| Branch / Tag | Version | Key Features |
|---|---|---|
| 1-basic / 1.0 | **v1.0 Basic** | ICT Liquidity Sweep + EMA9/21 + RSI7 + Demo Guard + Break-Even + Trailing Stop |
| 3-highspeed / 3.6 | **v3.6 HighSpeed** | High-Speed Scalper (M1), Cooldown Guard (1 bar), Dynamic ATR SL buffer |
| 4-hybrid / 4.0 | **v4.0 Hybrid** | TradingView Hall of Fame: LazyBear Squeeze Momentum + LuxAlgo Order Blocks (SMC) + UT Bot Trailing |
| 5-fortified / 5.0 | **v5.0 Fortified** | **แก้จุดอ่อน 14 จุด**: เพิ่ม H1 EMA20/50 Trend Filter, Strict AND Logic, Fixed LinReg, Max 15 Trades/Day, Losing Streak Limiter (3 losses), 3-bar Cooldown, CPU optimization |
| main | **Latest (v5.0)** | เวอร์ชันล่าสุดพร้อมเอกสารและระบบพร้อมใช้งานทันที |

---

## 🛠️ Indicators & Strategy Logic (v5.0 Fortified)

### 1. Higher Timeframe Trend Filter (H1) — ใช้งานจริง
- **ตัวชี้วัด:** EMA 20 และ EMA 50 บน Timeframe H1
- **เงื่อนไข:** 
  - BUY ได้ต่อเมื่อ H1 EMA20 > EMA50 และราคาอยู่เหนือ EMA20
  - SELL ได้ต่อเมื่อ H1 EMA20 < EMA50 และราคาอยู่ใต้ EMA20
  - หากตลาด Sideway / ไร้เทรนด์ บอทจะ **งดออกออเดอร์** เพื่อป้องกันการเทรดสวนทางใหญ่

### 2. LazyBear Squeeze Momentum — ใช้งานจริง
- **Bollinger Bands (20, 2.0)** vs **Keltner Channels (20, 1.5)**
- Squeeze Release (sqzOff): ตรวจจับจังหวะที่ความผันผวนระเบิดตัวออกจากการบีบอัด
- Linear Regression Momentum (al): วัดโมเมนตัมทิศทางราคาโดยแท้จริง (ถอดรหัสแบบเดียวกับ Pine Script)

### 3. LuxAlgo Smart Money Concepts (SMC) — ใช้งานจริง
- **Order Block (OB):** สแกนย้อนหลัง 30 แท่ง เพื่อหากรอบการเข้าซื้อขายของสถาบันการเงิน (Demand/Supply Zones)
- **Liquidity Sweep:** สแกนการกวาดสภาพคล่องจุดสูงสุด/ต่ำสุดของสวิงก่อนหน้า

### 4. Risk & Capital Protection ( Capital)
- **Fixed Lot:** 0.01
- **Risk:Reward:** 1:1.8
- **Break-Even:** เลื่อน SL บังหน้าทุนทันทีเมื่อกำไรถึง 0.8R
- **Trailing Stop:** UT Bot Safe Dynamic Trailing เมื่อกำไรเกิน 1.2R
- **Daily Drawdown Kill Switch:** ปิดการเทรดอัตโนมัติหาก Equity ร่วงเกิน 10%
- **Max Trades Per Day:** สูงสุด 15 ไม้/วัน (ป้องกัน Overtrading)
- **Losing Streak Limiter:** หากแพ้ติดกัน 3 ไม้ บอทจะหยุดพักทันที

---

## 🚀 Installation & Deployment

1. คัดลอกไฟล์ .mq5 ไปที่โฟลเดอร์ MT5:
   `AppData\Roaming\MetaQuotes\Terminal\<ID>\MQL5\Experts\Advisors\`
2. เปิด MetaEditor แล้วกด **Compile (F7)**
3. ลาก EA ลงบนกราฟ **XAUUSD (Timeframe M1 หรือ M5)**
4. ตรวจสอบว่าปุ่ม **Algo Trading** ใน MT5 เป็นสีเขียว
