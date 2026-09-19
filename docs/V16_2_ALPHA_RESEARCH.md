# V16.2 Alpha Research Specification & Protocol
> **Status:** Quantitative Research Protocol (Strictly Passive / Non-Execution Phase)  
> **Symbol:** XAUUSD | **Platform:** MetaTrader 5 (XM Global Environment)  
> **Primary Directive:** Zero Trade Execution during Data Collection; Server-Side Hard SL on 100% of Orders upon Live Deployment

---

## 1. Safety & Data Integrity Invariants

1. **Zero Data Leakage:**
   * ตัวแปร Features ในช่วงเวลา $t$ ต้องคำนวณจากข้อมูลที่ปิดแล้ว ($t \le 0$) เท่านั้น
   * `Forward Return` ($t+5, t+15$) คือ **Ex-post Label** ที่คำนวณแบบ Offline ทีหลัง ห้ามให้ Engine สแกนหรือบันทึกในเวลาจริงที่อาจทำให้โมเดลมองเห็นอนาคต (Look-ahead bias)
2. **Strict Chronological Splitting (Purged Walk-Forward):**
   * ห้ามใช้วิธี Random Shuffle หรือ Standard K-Fold CV เด็ดขาด
   * แบ่ง Train (In-Sample) และ Test (Out-of-Sample) ตามเส้นเวลา (Time-series Split) พร้อมใส่ Purging / Embargo Window เท่ากับระยะ Forward Return ป้องกันข้อมูลทับซ้อน
3. **Accurate Taxonomy (TV-VWAP):**
   * เรียกชื่อ **"Tick-Volume VWAP (TV-VWAP)"** ให้ถูกต้องตามความเป็นจริงบน MT5 ห้ามเคลมว่าเป็น Centralized Real Traded Volume
4. **Mandatory Hard SL Broker Compliance:**
   * ตรวจสอบ `SYMBOL_TRADE_STOPS_LEVEL` และ `SYMBOL_TRADE_FREEZE_LEVEL` ก่อนส่งคำสั่งเสมอ
   * ระยะ SL ต้องมากกว่า Minimum Stop Distance เสมอ
   * มี Error Handling ดักจับ Return Code: Requote (10004), Slippage Exceeded, Order Rejected

---

## 2. XM Infrastructure & Session Calibration

### 2.1 XM Server Timezone & DST Matrix
โบรกเกอร์ XM อิงเวลาเซิร์ฟเวอร์ตามเวลาไซปรัส/ยุโรปตะวันออก (EET / EEST) ซึ่งออกแบบให้ตรงกับตลาดปิดของนิวยอร์ก (17:00 NY = 00:00 Server Time):
* **Winter (EET: UTC+2):** London Session = 10:00 - 18:30 Server Time, NY Session = 15:30 - 22:00 Server Time
* **Summer (EEST: UTC+3):** London Session = 10:00 - 18:30 Server Time, NY Session = 15:30 - 22:00 Server Time
* **Rule:** ดึง `TimeTradeServer()` เทียบกับเวลา GMT แบบไดนามิก ห้าม Hardcode Time Offset เดี่ยวๆ

### 2.2 XM Real Spread Distribution Profiling
* ข้อมูล Telemetry เดิม (2 Sessions) ยังไม่เพียงพอในการสร้างโมเดลต้นทุน
* ต้องเก็บข้อมูลสเปรดสด $\ge 15$ Sessions เพื่อสร้าง Spread Distribution:
  * Median Spread ($S_{50}$)
  * 95th Percentile Spread ($S_{95}$)
  * Spread Surge Cutoff ($S_{\text{limit}} = S_{95} \times 1.2$)

---

## 3. Candidate Research Feature Matrix

```
[ Feature Space (t <= 0) ]
├── 1. KER Noise Filter: Kaufman Efficiency Ratio M1, n ∈ {10, 15, 20, 30}
├── 2. TV-VWAP Dispersion: Distance to London / NY Anchored TV-VWAP (z-scores)
├── 3. Tick Arrival Intensity: Ticks per minute normalized against 30-bar rolling mean
├── 4. Relative Spread Cost: Current Spread / ATR(14)_M1
└── 5. Macro Window Binary Gate: IsInNewsLockout (-30m ถึง +30m USD High Impact)
```

---

## 4. Multi-Metric Deployment Gates (เกณฑ์การผ่านสู่ Production)

ระบบจะ **ไม่อนุญาต** ให้เข้าสู่ Production จนกว่าจะผ่านเกณฑ์เชิงปริมาณครบทุกข้อ:

| Metric | Threshold เกณฑ์ผ่าน | วัตถุประสงค์การวัดผล |
| :--- | :--- | :--- |
| **Sample Size** | $N \ge 100$ Trades (บน OOS/Demo) | ป้องกัน Small Sample Bias |
| **Profit Factor (Net)** | $\ge 1.30$ (หัก Spread, Comm, Swap จริง) | ยืนยันกำไรสุทธิหลังต้นทุนเสียดทาน |
| **Statistical T-Stat** | $t > 2.0$ ($p < 0.05$) | ยืนยันว่าผลลัพธ์ไม่ได้เกิดจากความบังเอิญ |
| **Max Consecutive Losses** | $\le 4$ ครั้ง | ป้องกันภาวะ Drawdown กระชากลึก |
| **Max Daily Equity DD** | $< 3.0\%$ จาก High-Water Mark | กฎเหล็ก Capital Preservation Guardian |
| **Hard SL Compliance** | **100% (Zero Missed/Rejected SL)** | ความปลอดภัยสูงสุดระดับโครงสร้างพื้นฐาน |

---

## 5. แผนการดำเนินงาน 7 ขั้นตอน (7-Step Research Pipeline)

```
[ Step 1: Telemetry Collector ]
  └── รันสคริปต์ Passive Logging บน MT5 (ห้ามยิง Order เด็ดขาด)
       │
[ Step 2: Longitudinal Data Collection ]
  └── บันทึกข้อมูล M1 Features และ Spreads ต่อเนื่อง ≥ 15 Trading Sessions
       │
[ Step 3: Offline Label Generation ]
  └── รัน Python สคริปต์สร้าง Labels (Forward Return t+5, t+15) แยกอิสระจาก Features
       │
[ Step 4: In-Sample Optimization & Parameter Freeze ]
  └── ทำ Walk-forward Analysis บนชุด In-Sample แล้ว "ล็อคพารามิเตอร์ตายตัว" (Freeze)
       │
[ Step 5: Out-of-Sample (OOS) Validation ]
  └── ทดสอบชุดพารามิเตอร์ที่ Freeze แล้วบน OOS Data (≥ 15 Sessions)
       │
[ Step 6: Forward Demo Soak Test ]
  └── นำเข้าทดสอบ Forward จริงบนบัญชี Demo: 112468807
       │
[ Step 7: Production Staging Gate ]
  └── ตรวจสอบผ่านเกณฑ์ Multi-Metric Gate 100% ก่อนบรรจุเข้า Master EA
```
