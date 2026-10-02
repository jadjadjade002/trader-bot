# QuantumTitan V23 — Liquidity Retest Fade (LRF Engine)

[![Platform](https://img.shields.io/badge/Platform-MetaTrader%205-blue.svg)](https://www.metatrader5.com/)
[![Language](https://img.shields.io/badge/Language-MQL5-orange.svg)](https://www.mql5.com/)
[![Asset](https://img.shields.io/badge/Asset-XAUUSD%20(Gold)-gold.svg)]()
[![Status](https://img.shields.io/badge/Live%20Status-Active%20%2B130%25%2B-brightgreen.svg)]()

ระบบเทรดอัตโนมัติ MetaTrader 5 (MQL5) ระดับ Quantitative สำหรับสินทรัพย์ **XAUUSD (Gold)** บนกรอบเวลา **M1** ทำงานด้วยกลยุทธ์ **Donchian False Breakout Fade (Liquidity Sweep Reversal)** เพื่อดักจับสภาพคล่อง (Liquidity Sweeps) และการทะลุหลอก (False Breakouts) ของรายย่อย พร้อมระบบ **Consecutive Loss Circuit Breaker** ตัดวงจรความเสี่ยงอัตโนมัติ

---

## 1. ผลการทดสอบเดินหน้าสด (Live Forward-Test Performance)

บอทถูกติดตั้งและรันสดบนบัญชีจริงจำลอง (Demo Account `5056497798`, Server: `MetaQuotes-Demo`, เลเวอเรจ 1:200):

* **เงินทุนตั้งต้น (Initial Deposit):** $70.00 USD (25 ก.ย. 2026)
* **ยอดบาลานซ์ปัจจุบัน (Current Balance):** **$158.74 USD**
* **มูลค่าพอร์ตสุทธิ (Current Equity):** **$162.13 – $170.77 USD**
* **ผลตอบแทนสุทธิ (Net Gain):** **+131.6% ถึง +144.0% (กำไรเกินเท่าตัวใน ~1 สัปดาห์)**
* **อัตราชนะ (Win Rate):** **~39.6%**
* **อัตราส่วนผลตอบแทนต่อความเสี่ยง (Risk:Reward):** **1 : 2.0 (2.0R Asymmetric Payoff)**
* **ไม้ที่ปิดรอบแล้ว (Closed Roundtrips):** 96+ ไม้

---

## 2. ทำไมกลยุทธ์ Liquidity Fade ถึงสร้างกำไรสูงใน M1?

ตามตำราเทรดทั่วไป เมื่อราคาเบรกกรอบ High/Low 20 แท่งและทำการ Retest ยืนโซน รายย่อยมักแห่เปิด **BUY/SELL ตามเทรนด์** แต่ในโครงสร้างจุลภาค (Market Microstructure) ของทองคำบนแท่ง M1:

1. **ธรรมชาติของ M1 คือ Fakeout > 70%:** การเบรกส่วนใหญ่บนแท่ง 1 นาที เป็นเพียงการ "กวาดสภาพคล่อง (Liquidity Hunt)" ของรายใหญ่ ไม่ใช่เทรนด์จริง
2. **กลไกการดักจับของ V23 (Liquidity Fade Engine):**
   * เมื่อเกิดสัญญาณเบรกบนแล้วชะลอตัว $\rightarrow$ **V23 เปิด SELL** ดักจับจังหวะเทกลับเข้ากรอบ
   * เมื่อเกิดสัญญาณเบรกล่างแล้วชะลอตัว $\rightarrow$ **V23 เปิด BUY** ดักจับจังหวะดีดกลับเข้าสู่สมดุล
3. **ความได้เปรียบทางคณิตศาสตร์ (Positive Expectancy):**
   * เวลาแพ้: โดนตัดขาดทุนสั้นๆ ที่ $1.5\times$ ATR (~$2.50 – $3.50)
   * เวลาชนะ: ราคาวิ่งทุบกลับเข้ากรอบ ชนเป้ากำไร 2.0R (~$5.50 – $11.50)
   * แม้อัตราชนะเพียง 40% แต่ค่าเฉลี่ยกำไรโตเป็น 2 เท่าของผลขาดทุน ทำให้พอร์ตเติบโตอย่างมั่นคง

---

## 3. สถาปัตยกรรมและการควบคุมความเสี่ยง (Risk Management)

| มาตรการความปลอดภัย | การตั้งค่า | รายละเอียดการทำงาน |
|---|---|---|
| **Strategy Mode** | Liquidity Fade | ดักจับการทะลุหลอกและดึงราคากลับเข้ากรอบ Mean Reversion |
| **Execution Mode** | `InpEnableSessionGuard = false` | โหมด 24 ชั่วโมง เทรดได้ต่อเนื่องทั้งวันเมื่อมี Setup เกิดขึ้น |
| **Circuit Breaker** | `InpEnableCircuitBreaker = true` | **หยุดพักอัตโนมัติ 90 นาที** เมื่อแพ้ติดกัน 4 ไม้ (`MaxLosses = 4`) ป้องกันช่วงตลาดมี Super-Trend ข่าวสงคราม |
| **Max 1 Position** | `HasOpenPosition()` | ถือได้ครั้งละ 1 ไม้เท่านั้น ไม่เบิ้ล ไม่ Grid ไม่ Martingale |
| **Emergency Hard SL** | `InpEnableHardSL = true` | ส่งคำสั่ง Stop Loss ฝั่งเซิร์ฟเวอร์โบรกเกอร์ทันทีทุกไม้ กันระบบหลุด/ไฟดับ |
| **Time-Based Exit** | `InpMaxHoldBars = 60` | หากถือออเดอร์ครบ 60 แท่ง M1 (1 ชั่วโมง) แล้วยังไม่ชน TP/SL บอทจะ Cut ทันที |

---

## 4. โครงสร้างโฟลเดอร์ของโปรเจกต์ (Project Structure)

โปรเจกต์จัดโครงสร้างแบบ Clean Architecture โดยแสดงเฉพาะเวอร์ชันหลักที่ใช้งานจริงไว้ที่ Root:

```text
trader-bot/
├── QuantumTitan_v23_LondonRetestBreakout.mq5   # [ACTIVE] ซอร์สโค้ด EA หลักเวอร์ชัน 23
├── QuantumTitan_v23_LondonRetestBreakout.ex5   # [ACTIVE] ไบนารีคอมไพล์พร้อมใช้งาน
├── README.md                                   # คู่มือและเอกสารสรุปผลงาน
├── AGENTS.md / GEMINI.md                       # ข้อกำหนดและโหมดการทำงานของ Agent
├── versions/                                   # โฟลเดอร์เก็บเวอร์ชันเก่าและชุดทดลองย้อนหลัง
│   ├── QuantumTitan_v9_Singularity.*           # V9 สถาปัตยกรรมโมดูล
│   ├── QuantumTitan_v10_Singularity.*          # V10 Stress test
│   ├── QuantumTitan_v11_Singularity.*          # V11 HUD Dashboard
│   ├── QuantumTitan_v12_Singularity.*          # V12 Multi-Timeframe
│   ├── QuantumTitan_v13_Singularity.*          # V13 Macro Brain
│   ├── QuantumTitan_v14_Apex.*                 # V14 8-Factor Confluence
│   ├── QuantumTitan_v15_Apex.*                 # V15 Fast Scalper
│   ├── QuantumTitan_v16_*                      # V16 M1 Precision / State Transition
│   ├── QuantumTitan_v17 - v22_*                # V17-V22 Precision & Swing Research
│   ├── QuantumTitan_v25_*                      # V25 Forward Gate Experiments
│   └── logs/                                   # บันทึกการคอมไพล์ของเวอร์ชันเก่า
├── docs/                                       # เอกสารเชิงลึก, บทวิเคราะห์, และภาพประกอบ
│   └── V23_CANDIDATE_VERIFICATION_REPORT.md    # รายงานการตรวจสอบ Candidate V23
├── scripts/                                    # สคริปต์อัตโนมัติสำหรับการ Deploy และตรวจสอบ
│   ├── deploy_v23_vm.py                        # สคริปต์ติดตั้งและอัปเดตบอทขึ้น VM อัตโนมัติ
│   ├── run_remote_stats.py                     # คำนวณสถิติ Win Rate และ PnL จาก VM สด
│   └── compile.ps1                             # สคริปต์คอมไพล์ผ่าน MetaEditor CLI
├── research/                                   # โมเดลค้นคว้า Quant Research & Alpha Search
└── tests/                                      # ชุดทดสอบ Unit Tests ด้วย Pytest
```

---

## 5. การติดตั้งและใช้งาน (Deployment Guide)

### 1) การคอมไพล์ซอร์สโค้ด
ใช้ PowerShell สั่งรันคอมไพล์ผ่าน MetaEditor:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/compile.ps1 QuantumTitan_v23_LondonRetestBreakout
```

### 2) การติดตั้งบน MetaTrader 5
1. คัดลอก `QuantumTitan_v23_LondonRetestBreakout.ex5` ไปไว้ที่โฟลเดอร์ `MQL5/Experts/`
2. เปิดชาร์ต **XAUUSD** กรอบเวลา **M1**
3. ลาก EA ลงบนชาร์ต และตั้งค่าพารามิเตอร์:
   * `InpEnableSessionGuard = false` (รัน 24 ชั่วโมง)
   * `InpEnableCircuitBreaker = true` (เปิดระบบตัดวงจรความเสี่ยง)
   * `InpLotSize = 0.01` (หรือ 0.02 ตามขนาดพอร์ต)
4. เปิดปุ่ม **Algo Trading** บนแถบเครื่องมือของ MT5

---

## 6. ลิขสิทธิ์และข้อจำกัดความรับผิดชอบ (Disclaimer)
ระบบนี้สร้างขึ้นเพื่อการศึกษาและการวิจัยเชิงปริมาณ (Quantitative Research) ตลาดอนุพันธ์มีความเสี่ยงสูง ควรทดสอบบนบัญชีทดลอง (Demo Account) จนมั่นใจก่อนใช้งานด้วยเงินทุนจริง
