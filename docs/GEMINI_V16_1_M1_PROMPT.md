# Gemini Build Prompt: QuantumTitan V16.1 M1

## Objective

สร้างบอท `QuantumTitan_v16_1_M1` สำหรับ XAUUSD M1 โดยต่อยอดจากพฤติกรรมของ V16 ที่ใช้งานอยู่บนบัญชี `112334471` แต่ต้องเพิ่มคุณภาพสัญญาณและปรับ trade management ดังนี้:

1. เปิดออเดอร์เฉพาะเมื่อสัญญาณมีความมั่นใจสูงกว่า V16 เดิม
2. ขยาย TP จาก V16 เดิมอย่างมีหลักฐานรองรับ ไม่ใช่เพิ่มแบบสุ่ม
3. ขยับ SL กันหน้าทุนช้าลงเล็กน้อย เพื่อให้ position มีพื้นที่วิ่งมากขึ้น
4. นำ failure modes ที่พบจากการใช้งาน V16 มาป้องกันใน V16.1
5. ใช้งานทดลองเฉพาะบัญชี `112468807`

## Account and isolation policy

### Protected account

บัญชี `112334471` เป็น V16 production/demo เดิม ห้ามแตะโดยเด็ดขาด:

- ห้ามปิด terminal หรือ chart
- ห้ามแก้ input
- ห้ามถอด EA
- ห้ามเปลี่ยน magic number
- ห้าม restart process ที่เป็นของบัญชีนี้
- ห้าม deploy binary หรือ profile ไปยัง data directory ของบัญชีนี้

### Authorized test account

บัญชี `112468807` เป็นบัญชีที่ได้รับอนุญาตให้ใช้ V16.1:

- ต้องตรวจว่าเป็น demo account ก่อน deploy
- ต้องยืนยัน account login จาก MT5 terminal เอง
- ต้องใช้ terminal/data directory/profile แยกจาก V16 เดิม
- ต้องใช้ magic number ใหม่ที่ไม่ซ้ำกับ V16
- ห้ามสมมติว่าบัญชีที่ถูกเลือกใน Navigator คือบัญชีที่ EA กำลังรันอยู่ ต้องยืนยันจาก journal, chart และ login state

ถ้ายืนยัน account ไม่ได้ ให้หยุด ห้าม deploy

## Required first phase: understand V16 fully

ก่อนแก้โค้ดต้องอ่านและสรุปไฟล์ต่อไปนี้:

- `QuantumTitan_v16_Velocity.mq5`
- `QuantumTitan_v16_Apex.mq5`
- `Include/QuantumTitan/AlphaScoring.mqh`
- `Include/QuantumTitan/TrailingSafety.mqh`
- `Include/QuantumTitan/DynamicGrid.mqh`
- `docs/V16_BOT_ARCHITECTURE.md`
- `docs/V16_LIVE_STATUS_20260910.md`
- `deploy/v16_20260910_mql5.log`

ต้องระบุให้ชัดว่า V16.1 ต่อจาก `Velocity M1` หรือใช้ Apex module ใด ห้ามรวม Apex/grid เข้ามาโดยอัตโนมัติถ้า objective คือ M1 single-position bot

## Required V16 failure analysis

ใช้หลักฐานจริงจาก V16 เท่านั้น แยกเป็น observed, derived และ unknown

ต้องวิเคราะห์อย่างน้อย:

- false entries และ whipsaw
- spread สูงตอนเปิดออเดอร์
- slippage และราคาที่ได้จริง
- TP สั้นเกินไปหรือไม่
- BE trigger เร็วเกินไปหรือไม่
- loss ที่เกิดก่อน BE
- loss หลัง BE จากการย้าย SL
- BUY/SELL asymmetry
- signal ในช่วง rollover หรือ spread widening
- repeated entry หลังปิดออเดอร์
- broker stop/freeze level rejection
- duplicate position และ magic isolation
- log ที่ไม่มี explicit PnL

ห้ามสรุป winrate หรือ account PnL ถ้าไม่มี MT5 History/statement ที่ตรวจสอบได้

## V16 baseline to preserve

V16 Velocity baseline ที่ต้องบันทึกก่อนเปลี่ยน:

```text
timeframe: M1
magic: 991602
max spread: 60 points
TP: 180 points
SL: 260 points
BE trigger: 85 points
BE lock: 15 points
cooldown: 1 M1 bar
```

V16.1 ต้องใช้ magic ใหม่ เช่น `991612` หรือค่าที่ตรวจแล้วว่าไม่ชนกับ position/EA อื่น

ห้ามแก้ทับ `QuantumTitan_v16_Velocity.mq5` ให้สร้างไฟล์ใหม่:

```text
QuantumTitan_v16_1_M1.mq5
```

## V16.1 strategy requirements

### Higher-confidence entry

ต้องรักษา core logic ของ Velocity แต่เพิ่ม confirmation อย่างน้อย:

- EMA14/EMA50 trend alignment
- completed M1 candle เท่านั้น ห้ามใช้ active candle เป็น signal
- pullback/retest condition
- rejection wick/body confirmation
- RSI regime filter
- ATR minimum/noise filter
- spread filter
- cooldown after close
- one active position per symbol and V16.1 magic

กำหนดคะแนนหรือ hard gates ให้ตรวจสอบได้ ห้ามใช้คำว่า high confidence โดยไม่มี threshold ที่ระบุใน code และ log

ห้ามเปิดเพราะ indicator เดียว และห้ามเพิ่มจำนวนออเดอร์เพื่อให้ได้จำนวนมากขึ้น

### TP expansion

อย่าเปลี่ยน TP เป็นค่าตายตัวแบบเดาสุ่ม ให้เลือกวิธีใดวิธีหนึ่งและพิสูจน์ด้วย test:

- fixed TP ที่สูงกว่า 180 points
- ATR-based TP
- partial/target management หาก implementation ปลอดภัย

ต้องแสดงตารางเปรียบเทียบ V16 กับ V16.1:

```text
TP points or formula
SL points or formula
expected R
minimum spread condition
```

TP ใหม่ต้องผ่าน spread/slippage sanity check และต้องไม่ทำให้ reward target เป็นไปไม่ได้เมื่อเทียบกับ volatility ของ XAUUSD M1

### Slower breakeven

BE ต้องช้ากว่า V16 เดิมที่ 85 points แต่ต้องกำหนดค่าใหม่จาก test เช่น:

- `InpBreakevenTriggerPts > 85`
- `InpBreakevenLockPts >= 0`

ห้ามขยับ SL ถอยหลัง ห้ามย้าย SL ก่อน trigger และห้ามส่ง modify ซ้ำโดยไม่จำเป็น

ต้องทดสอบทั้ง BUY และ SELL:

- ก่อน trigger: SL เดิมไม่เปลี่ยน
- ถึง trigger: SL ย้ายไปตาม lock rule
- หลัง trigger: SL เคลื่อนไปทางป้องกันกำไรเท่านั้น
- broker stop/freeze level ไม่ผ่าน: log rejection และไม่ทำให้ EA crash

## Risk and safety requirements

- Demo-only guard ต้องคงอยู่
- Base lot ต้องไม่เกิน V16 baseline โดยไม่มี explicit approval
- ห้าม grid, martingale, recovery order หรือ averaging down
- ห้ามใช้ RiskGuard เพื่อเพิ่มความเสี่ยงหรือ bypass safety
- daily loss cutoff ต้องเป็น fail-safe ถ้ามีใน architecture
- spread gate ต้องทำงานก่อน order send
- ตรวจ free margin ก่อนเปิด order
- one position per symbol/magic เท่านั้น
- ตรวจ `PositionSelectByTicket` ก่อนแก้หรือปิด position
- ใช้ unique comment และ magic ใหม่สำหรับ audit
- เขียนเหตุผล signal และ rejection ลง log แบบไม่ใส่ secret

## Required inputs

ตั้งชื่อ input ชัดเจนและแสดง default ที่ใช้จริง:

```text
InpDemoOnly
InpMagicNumber
InpMaxSpreadPoints
InpBaseLot
InpTakeProfitPoints หรือ ATR TP parameters
InpStopLossPoints หรือ ATR SL parameters
InpBreakevenTriggerPts
InpBreakevenLockPts
InpCooldownBars
InpMinAtrPoints
InpMinConfidenceScore
InpEnableHUD
```

อย่าซ่อนค่าที่สำคัญไว้เป็น magic constant

## Validation before deployment

ต้องทำตามลำดับนี้:

1. compile ใหม่และตรวจ errors/warnings
2. unit tests สำหรับ signal gates และ trade management
3. backtest V16 baseline เทียบ V16.1 บนช่วงข้อมูลเดียวกัน
4. holdout test ที่ไม่ใช้ปรับ parameter
5. spread/slippage sensitivity test
6. test no-trade ในช่วง spread สูง
7. test no-trade ในช่วง insufficient ATR
8. test duplicate position/magic isolation
9. test restart/reconnect state
10. static scan ห้ามมี account `112334471` hard-coded ใน deploy profile ของ V16.1

ห้ามใช้ผล backtest อย่างเดียวเพื่ออ้างว่า winrate 80% หรือกำไรแน่นอน

## Deployment plan for account 112468807

deploy ได้ต่อเมื่อทุกข้อผ่าน:

- account ที่เปิดอยู่ยืนยันเป็น `112468807`
- terminal เป็น instance/data directory แยก
- V16.1 compile ผ่าน
- tests และ holdout ผ่านเกณฑ์ที่ระบุ
- magic ใหม่ไม่ชน
- chart เป็น XAUUSD M1
- EA name บน chart เป็น `QuantumTitan_v16_1_M1`
- Algo Trading status ถูกตรวจแล้ว
- initial lot และ spread limit ถูกตรวจแล้ว
- มี rollback command ที่ปิดเฉพาะ V16.1 instance
- V16 เดิมบน 112334471 ยังทำงานเหมือนเดิมและไม่ได้ถูกแก้

หลัง deploy ให้ตรวจ read-only:

- account login number
- chart symbol/timeframe
- EA name
- magic number
- open position count
- journal initialization
- first signal/rejection reason

ห้ามเปิด order ทันทีเพื่อทดสอบด้วยมือ และห้าม force signal

## Rollback plan

ถ้าเกิด error, account mismatch, duplicate magic, unexpected order, crash หรือ spread anomaly:

1. ปิดเฉพาะ V16.1 chart/terminal ของบัญชี 112468807
2. ห้ามปิดหรือ restart V16 ของ 112334471
3. เก็บ journal/log ก่อน cleanup
4. รายงาน ticket, error code, account, symbol, magic และ timestamp
5. ห้าม redeploy จนกว่า root cause จะถูกยืนยัน

## Deliverables

ต้องส่งมอบ:

```text
QuantumTitan_v16_1_M1.mq5
compiled binary and compile log
tests/test_v16_1_m1.py
docs/V16_1_DESIGN.md
docs/V16_1_VALIDATION.md
docs/V16_1_DEPLOYMENT_CHECKLIST.md
```

หาก validation ไม่ผ่าน ให้ส่งเฉพาะ report และ source ที่ยังไม่ deploy พร้อมระบุ blocker

## Final response requirements

ตอบเป็นภาษาไทยและระบุ:

- สิ่งที่เปลี่ยนจาก V16
- เหตุผลของ TP และ BE ใหม่
- หลักฐานจาก V16 ที่ใช้แก้
- test/backtest/holdout results
- known limitations
- account และ terminal ที่ deploy จริง
- magic number
- ยืนยันว่า 112334471 ไม่ถูกแตะ
- ยืนยันว่า 112468807 เป็น demo และได้รับอนุญาต
- rollback procedure

ห้ามใช้คำว่า “ชัวร์”, “กำไรแน่นอน”, “winrate 80% รับประกัน” หรือ “พร้อมใช้จริง” หากไม่มีหลักฐานรองรับ

## Absolute prohibitions

- ห้าม deploy ไป `112334471`
- ห้ามแก้หรือ overwrite V16 เดิม
- ห้ามแก้ broker/account credentials
- ห้ามส่งคำสั่ง trade เพื่อทดสอบ
- ห้ามเพิ่ม lot เพื่อชดเชย TP ที่ขยาย
- ห้ามใช้ข้อมูลอนาคตใน backtest
- ห้ามเลือกช่วงทดสอบที่ทำให้ผลดีโดยไม่มี holdout
- ห้าม commit หรือ push GitHub
