# QuantumSniper v5.0 Fortified — Walkthrough

## สิ่งที่ทำ

สร้างเวอร์ชัน **v5.0 Fortified** จากฐาน v4.0 Hybrid แก้ไขจุดอ่อนทั้ง **14 จุด** ที่ค้นพบ

## ไฟล์ที่สร้าง

| ไฟล์ | สถานะ |
|------|--------|
| [QuantumSniper_v5_Fortified.mq5](file:///C:/Users/USER/AppData/Roaming/MetaQuotes/Terminal/D0E8209F77C8CF37AD8BF550E51FF075/MQL5/Experts/Advisors/QuantumSniper_v5_Fortified.mq5) | ✅ Compiled (0 errors, 0 warnings) |
| [QuantumSniper_v5_Fortified.ex5](file:///C:/Users/USER/AppData/Roaming/MetaQuotes/Terminal/D0E8209F77C8CF37AD8BF550E51FF075/MQL5/Experts/Advisors/QuantumSniper_v5_Fortified.ex5) | ✅ Ready to deploy |

## รายการแก้ไข 14 จุด

### 🔴 Critical (3 จุด)

1. **OR→AND ใน Scoring** — candle confirmation ต้องเป็นทั้งแท่งปัจจุบันและแท่งก่อน (ไม่ใช่อย่างใดอย่างหนึ่ง)
2. **BUY/SELL Exclusive** — ถ้าทั้ง 2 ฝั่งมีสัญญาณพร้อมกัน → ข้ามไม่เทรด (ตลาดคลุมเครือ)
3. **H1 Trend Filter** — เพิ่ม EMA20/50 บน H1 เป็นตัวกรอง ห้ามเทรดสวนเทรนด์ใหญ่

### 🟠 High (4 จุด)

4. **Max Trades/Day (15) + Losing Streak (3)** — นับจำนวนเทรดจาก deal history ถ้าเสีย 3 ครั้งติดจะหยุดพัก
5. **LinReg Fix** — คืนค่า `intercept + slope*(length-1)` ตรงกับ Pine Script `linreg()` 
6. **OB Extended Lookback** — ขยายจาก 6 bars เป็น 30 bars + ลด body ratio จาก 0.8 เป็น 0.6
7. **BE Initial Risk** — เก็บ risk เดิมไว้ตั้งแต่เปิดออเดอร์ ไม่คำนวณใหม่จาก SL หลัง BE

### 🟡 Medium (4 จุด)

8. **Magic Number** — เปลี่ยนเป็น 550500 ไม่ชนกับ v3/v4 (777888)
9. **Spread Block** — update `m_lastBarTime` เมื่อ spread สูง ไม่ลองซ้ำในแท่งเดิม
10. **SMC AND Logic** — ต้องมีทั้ง Order Block + Liquidity Sweep (ไม่ใช่แค่อย่างใดอย่างหนึ่ง)
11. **Cooldown 3 Bars** — จาก 1 bar (60 วิ) เป็น 3 bars (3 นาที)

### 🔵 Low (3 จุด)

12. **ATR Bar 0** — ใช้ ATR bar ปัจจุบัน ไม่ใช่ bar 1
13. **Trade Result Check** — ตรวจ `ResultRetcode()` หลังส่งออเดอร์ Print error ถ้าไม่สำเร็จ
14. **SQZ Calc on New Bar** — คำนวณ Squeeze/SMC แค่ตอนเปลี่ยนแท่ง ประหยัด CPU

## Dashboard ใหม่

HUD v5.0 แสดงข้อมูลเพิ่ม:
- **H1 Trend Bias** — BULLISH ↑ / BEARISH ↓ / RANGING ↔
- **Trades Today** — 0/15
- **Losing Streak** — 0/3
- **Daily DD** — 0.0% / 10%

## วิธีใช้งาน

1. ใน MT5 ลาก **QuantumSniper_v5_Fortified** ลงบนชาร์ต XAUUSD M1 หรือ M5
2. ลบ EA เดิม (v3/v4) ออกก่อน (ป้องกัน Magic Number ชนกัน)
3. ตรวจสอบว่า H1 Trend Bias แสดง BULLISH หรือ BEARISH (ไม่ใช่ RANGING) ก่อนจะเทรดได้
