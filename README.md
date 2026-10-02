# Aegis Predator — Institutional False Breakout Liquidity Engine

[![Platform](https://img.shields.io/badge/Platform-MetaTrader%205-blue.svg)](https://www.metatrader5.com/)
[![Language](https://img.shields.io/badge/Language-MQL5-orange.svg)](https://www.mql5.com/)
[![Asset](https://img.shields.io/badge/Asset-XAUUSD%20(Gold)-gold.svg)]()
[![Status](https://img.shields.io/badge/Live%20Status-Active%20%2B146%25-brightgreen.svg)]()

ระบบเทรดอัตโนมัติ MetaTrader 5 (MQL5) สถาปัตยกรรม Quantitative ขั้นสูงสำหรับสินทรัพย์ **XAUUSD (Gold)** บนกรอบเวลา **M1** ทำงานด้วยกลยุทธ์ **Donchian False Breakout Fade (Liquidity Sweep Reversal)** ดักจับสภาพคล่อง (Liquidity Hunts) และการทะลุหลอก (Trap Breakouts) ของรายย่อย พร้อมระบบ **Consecutive Loss Circuit Breaker** ตัดวงจรความเสี่ยงอัตโนมัติ

---

## 1. ผลการทดสอบเดินหน้าสด (Live Forward-Test Performance)

บอทถูกติดตั้งและรันสดบนบัญชีจริงจำลอง (Demo Account `5056497798`, Server: `MetaQuotes-Demo`, เลเวอเรจ 1:200):

* **เงินทุนตั้งต้น (Initial Deposit):** $70.00 USD (25 ก.ย. 2026)
* **ยอดบาลานซ์ปัจจุบัน (Current Balance):** **$172.36 USD**
* **กำไรสุทธิสะสม (Net PnL):** **+$102.36 USD (+146.2%)**
* **อัตราชนะ (Win Rate):** **40.9%**
* **อัตราส่วนผลตอบแทนต่อความเสี่ยง (Risk:Reward):** **1 : 2.0 (2.0R Asymmetric Payoff)**
* **จำนวนไม้ที่ปิดรอบแล้ว (Closed Roundtrips):** **110 ไม้**
* **สถานะความปลอดภัย (Circuit Breaker):** ทำงานสมบูรณ์ (ตัดพักความเสี่ยง 90 นาทีอัตโนมัติเมื่อชน 4 ไม้เสียติดกัน)

---

## 2. ปรัชญาการล่าสภาพคล่อง (Predator Liquidity Fade Engine)

ตามทฤษฎีการเทรดทั่วไป เมื่อราคาทะลุแนวรับ-แนวต้าน 20 แท่งและเกิดแท่งคอนเฟิร์มยืนโซน รายย่อยมักแห่เปิด **BUY/SELL ตามโมเมนตัม** แต่ในโครงสร้างจุลภาค (Market Microstructure) ของตลาดทองคำ M1:

1. **ธรรมชาติของ M1 คือ Fakeout > 70%:** การเบรกกรอบส่วนใหญ่เป็นเพียง "การกวาดสภาพคล่อง (Stop Hunt / Liquidity Sweep)" เพื่อเติมออเดอร์ของสถาบันใหญ่ ไม่ใช่เทรนด์ต่อเนื่องระยะยาว
2. **กลไกการล่าของ Aegis Predator:**
   * เมื่อเกิดสัญญาณเบรกทะลุแนวต้านบนแล้วชะลอตัว $\rightarrow$ **Aegis Predator ดักเปิด SELL** ดักสับคนติดดอย เก็บกำไรจังหวะราคาทุบกลับเข้ากรอบ
   * เมื่อเกิดสัญญาณหลุดแนวรับล่างแล้วชะลอตัว $\rightarrow$ **Aegis Predator ดักเปิด BUY** ดักช้อนจังหวะราคาดีดกลับเข้าสู่จุดสมดุล
3. **ความได้เปรียบทางคณิตศาสตร์ (Positive Expectancy):**
   * เวลาเสีย: ตัดขาดทุนสั้น $1.5\times$ ATR (~$2.50 – $3.50)
   * เวลาได้: รันกำไรชนเป้า 2.0R (~$5.50 – $11.50)
   * แม้อัตราชนะจะอยู่ที่ ~41% แต่ด้วยอัตรากำไรโตเป็น 2 เท่าของการตัดขาดทุน ทำให้พอร์ตเติบโตอย่างก้าวกระโดด

---

## 3. สถาปัตยกรรมและการควบคุมความเสี่ยง (Institutional Risk Controls)

| ระบบควบคุม | พารามิเตอร์ | รายละเอียดการทำงาน |
|---|---|---|
| **Strategy Core** | `InpFadeBreakouts = true` | ดักเก็บสภาพคล่องจากการทะลุหลอก (Liquidity Sweep Fade) |
| **Execution Window** | `InpEnableSessionGuard = false` | โหมด 24H Full-Alpha เทรดต่อเนื่องทุกช่วงเวลาเมื่อเกิด Setup คุณภาพ |
| **Circuit Breaker** | `InpEnableCircuitBreaker = true` | **หยุดพักอัตโนมัติ 90 นาที** เมื่อแพ้ติดกัน 4 ไม้ (`MaxLosses = 4`) ป้องกันช่วงตลาดมี Super-Trend ข่าวสงคราม |
| **Single Exposure** | `HasOpenPosition()` | จำกัดการถือครองครั้งละ 1 ไม้เท่านั้น ไม่เบิ้ล ไม่เบิ้ลล็อต ไม่ Grid ไม่ Martingale |
| **Broker-Side Hard SL** | `InpEnableHardSL = true` | ส่งคำสั่ง Stop Loss ฝั่งเซิร์ฟเวอร์โบรกเกอร์ทันทีทุกไม้ ป้องกันความเสี่ยงเซิร์ฟเวอร์หรืออินเทอร์เน็ตขัดข้อง |
| **Time Decay Exit** | `InpMaxHoldBars = 60` | หากถือออเดอร์ครบ 60 แท่ง M1 (1 ชั่วโมง) แล้วไม่ชน TP/SL บอทจะปิดทำกำไร/ตัดขาดทุนทันที |

---

## 4. โครงสร้างโปรเจกต์ (Clean Project Architecture)

โครงสร้างโฟลเดอร์ถูกจัดระเบียบให้แสดงเฉพาะโมเดลหลักที่ใช้งานจริงไว้ที่ Root:

```text
trader-bot/
├── AegisPredator.mq5                           # [ACTIVE] ซอร์สโค้ด EA หลัก Aegis Predator
├── AegisPredator.ex5                           # [ACTIVE] ไบนารีคอมไพล์พร้อมใช้งาน
├── README.md                                   # เอกสารภาพรวม สถิติ และคู่มือการใช้งาน
├── AGENTS.md / GEMINI.md                       # ข้อกำหนดและโหมดการทำงานของ Agent
├── versions/                                   # โฟลเดอร์จัดเก็บเวอร์ชันเก่า (V9 – V23, V25)
│   ├── QuantumTitan_v23_LondonRetestBreakout.* # V23 (ต้นแบบสถาปัตยกรรม Circuit Breaker)
│   ├── QuantumTitan_v16 - v22_*                # โมเดลวิจัยก่อนหน้า
│   └── logs/                                   # บันทึกการคอมไพล์ของเวอร์ชันเก่า
├── docs/                                       # เอกสารการทดสอบเชิงลึก และภาพแคปเจอร์
├── scripts/                                    # สคริปต์อัตโนมัติสำหรับการ Deploy และมอนิเตอร์ VM
│   ├── deploy_aegis_vm.py                      # ติดตั้งและรีสตาร์ต Aegis Predator บน VM
│   ├── run_remote_stats.py                     # คำนวณสถิติ Win Rate และ PnL จาก VM สด
│   └── compile.ps1                             # สคริปต์คอมไพล์ผ่าน MetaEditor CLI
├── research/                                   # งานวิจัยเชิงปริมาณ (Quant Research)
└── tests/                                      # ชุดทดสอบระบบอัตโนมัติ
```

---

## 5. การติดตั้งและใช้งาน (Deployment Guide)

### 1) การคอมไพล์ซอร์สโค้ด
ใช้ PowerShell สั่งรันคอมไพล์ผ่าน MetaEditor:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/compile.ps1 AegisPredator
```

### 2) การติดตั้งบน MetaTrader 5
1. คัดลอก `AegisPredator.ex5` ไปไว้ที่โฟลเดอร์ `MQL5/Experts/`
2. เปิดชาร์ต **XAUUSD** กรอบเวลา **M1**
3. ลาก EA ลงบนชาร์ต และตั้งค่าพารามิเตอร์:
   * `InpEnableSessionGuard = false` (รัน 24 ชั่วโมง)
   * `InpEnableCircuitBreaker = true` (เปิดระบบตัดวงจรความเสี่ยง)
   * `InpLotSize = 0.01` (หรือคำนวณตามขนาดพอร์ต)
4. เปิดปุ่ม **Algo Trading** บนแถบเครื่องมือของ MT5

---

## 6. ข้อจำกัดความรับผิดชอบ (Disclaimer)
ระบบนี้พัฒนาขึ้นเพื่อการวิจัยและการศึกษาเชิงปริมาณ ตลาดอนุพันธ์และทองคำมีความผันผวนสูง ควรทดสอบบนบัญชีจำลอง (Demo Account) จนเข้าใจพฤติกรรมของระบบอย่างถี่ถ้วนก่อนพิจารณาใช้งาน
