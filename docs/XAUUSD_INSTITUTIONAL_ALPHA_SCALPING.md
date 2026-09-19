# XAU/USD Quantitative Feature Research Playbook
> **Status:** Research & Hypothesis Catalog (NOT Production Bot Spec)  
> **Target Asset:** XAUUSD (MetaTrader 5 / XM Environment)  
> **Classification:** Experimental Feature Set for V16.2 Alpha Research

---

## 1. Reality Check & Caveats (ข้อจำกัดหน้างานจริงบน MT5)

| สมมติฐาน / ทฤษฎี | ความจริงบน MT5 / XM Broker | สถานะการใช้งาน |
| :--- | :--- | :--- |
| **COMEX Lead-Lag (15-80ms)** | MT5 ไม่มี Direct Feed หรือ Level 2 Order Book ของ CME GC ที่ซิงค์ระดับไมโครวินาที | ❌ **ตัดทิ้ง** (ไม่สามารถพิสูจน์หรือทำ Arbitrage บน MT5 ได้) |
| **Iceberg Absorption** | Tick Volume สูง + ราคาไม่วิ่ง อาจเกิดจาก Quote Flicker, LP Latency หรือ Spread Fluctuation ไม่ใช่ Iceberg เสมอไป | ⚠️ **เป็นแค่สมมติฐาน** (ต้องเก็บ Log พิสูจน์) |
| **B-Book Hunting SL** | เป็นข้อสันนิษฐานเชิงจิตวิทยา ไม่มี Telemetry ยืนยันจาก XM | ❌ **ห้ามใช้เป็นฐานตั้งระบบ** |
| **Tick-volume VWAP** | เป็น VWAP จำลองจาก Tick ไม่ใช่ Centralized Real Traded Volume | ⚠️ **ใช้เป็น Relative Indicator เท่านั้น** |
| **Fixed Thresholds (`<0.35`, `2.5σ`)** | ตัวเลขสมมติฐาน ต้อง Optimize และทำ Walk-forward ทดสอบกับข้อมูลจริง | ⚠️ **ต้องผ่าน Data Validation ก่อน** |
| **Session Timings** | ลอนดอน/นิวยอร์ก มี Daylight Saving Time (DST: GMT+2 / GMT+3) | ⚠️ **ต้องคำนวณแบบ Dynamic DST ห้าม Hardcode** |
| **XM Spread Reality** | บัญชีจริง XM สเปรดทองไม่ได้แคบ $\le 15$ points เสมอไป (ปกติ 18–35+ points) | ⚠️ **ต้องใช้ Dynamic Spread Filter ตามสภาพจริง** |

---

## 2. Risk Critical: Hard SL vs. Stealth Exit

> [!CAUTION]
> **ห้ามใช้ Stealth SL เป็นตัวตัดขาดทุนหลักเด็ดขาด!**  
> หาก Terminal ค้าง, ไฟฟ้าดับ, VPS/เน็ตเวิร์กหลุด หรือเกิด News Gap ตลาดจะลากพอร์ตเสียหายไม่มีลิมิต

### สถาปัตยกรรม Stop Loss ที่ถูกต้อง (Dual-Layer Protection)

```
[ Dual-Layer SL Architecture ]
├── 1. Primary Safety (Mandatory): Hard SL ฝากไว้ที่ Server โบรกเกอร์เสมอ
│      └── ทำหน้าที่: Emergency Airbag ป้องกันกรณีระบบหลุด, ข่าวระเบิด, Terminal Crash
└── 2. Auxiliary Soft Exit (Optional): Algorithm-level Early Cut ในโค้ด EA
       └── ทำหน้าที่: ปิดทำกำไร/ตัดขาดทุนก่อนชน Hard SL เมื่อโครงสร้างเสีย (Structural Invalidation)
```

---

## 3. Vetted Research Features (ชุดเครื่องมือที่ผ่านเกณฑ์นำไปวิจัย)

### 3.1 Kaufman Efficiency Ratio (KER) Noise Gate
* **วัตถุประสงค์:** คัดกรองช่วง Brown Noise (สุ่ม/Chop) ออกจากช่วงที่มีการเคลื่อนที่จริง
* **สูตร:**
  $$\text{KER}_n = \frac{|\text{Close}_t - \text{Close}_{t-n}|}{\sum_{i=1}^{n} |\text{Close}_i - \text{Close}_{i-1}|}$$
* **Research Task:** ทดสอบหา Parameter $n$ ที่เหมาะสม (10, 15, 20, 30) และ Threshold จริงด้วยข้อมูล M1 Tick Data ย้อนหลัง

### 3.2 Session-Anchored VWAP (Tick-Volume Basis)
* **วัตถุประสงค์:** หาจุดสมดุลราคาเฉลี่ยตาม Tick Volume ภายในแต่ละ Session
* **การ Anchor:**
  * Anchor 1: London Open (ปรับตาม DST)
  * Anchor 2: NY Cash Open (ปรับตาม DST)
* **Research Task:** วัด Standard Deviation Bands ($\pm 1.0\sigma, \pm 1.5\sigma, \pm 2.0\sigma$) เพื่อประเมิน Probability of Reversion

### 3.3 Dynamic Spread & Slippage Gate
* **วัตถุประสงค์:** สกัดกั้นการออกออเดอร์เมื่อต้นทุน Execution สูงกว่า Expectancy
* **เงื่อนไข:**
  ```cpp
  long spread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
  if(spread > InpMaxAllowedSpread) return; // บล็อกทันที
  ```
* **Research Task:** สำรวจค่าเฉลี่ย Median Spread และ 95th Percentile Spread ของโบรกเกอร์ XM ในช่วงเวลาต่างๆ

### 3.4 Cooldown & Daily Loss Circuit Breakers
* เสียติดกัน 3 ไม้ $\rightarrow$ บังคับหยุดพัก 60–90 นาที
* Equity Drawdown ประจำวันแตะ Threshold $\rightarrow$ Soft/Hard Lockout ทันที

---

## 4. Verification & Deployment Roadmap

```
[ Phase 1: Logging & Feature Collection ]
  └── บันทึก KER, Tick Intensity, Spread จริง ลงไฟล์ CSV บน Forward Market
       │
[ Phase 2: Offline Backtesting & Parameter Tuning ]
  └── ทดสอบ Threshold แบบ Walk-Forward Analysis (WFA)
       │
[ Phase 3: Holdout Validation (≥ 15 Trading Sessions) ]
  └── ตรวจสอบว่าระบบมี Positive Expectancy นอกชุดข้อมูล In-Sample
       │
[ Phase 4: Forward Demo Deployment ]
  └── รันบนบัญชี Demo เพื่อทดสอบ Execution Latency, Slippage, และ Broker Fills
       │
[ Phase 5: Production Staging ]
  └── ค่อยพิจารณาบรรจุเข้า EA สถาปัตยกรรมหลัก (พร้อม Hard SL 100%)
```
