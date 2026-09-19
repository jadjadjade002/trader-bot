# V16.2 Read-Only Telemetry Collector — Design & Verification Specification
> **Document Version:** 1.2 (Patched: Pure Status Schema, VM Diagnostic Fields, UTC-Aligned Sessions)  
> **Source Component:** `QuantumTitan_V16_2_TelemetryCollector.mq5`  
> **Test Suite:** `tests/test_v16_2_telemetry.py` (14 Unit Tests)  
> **Safety Mode:** Strictly Read-Only (Non-Trading / Zero Execution)  
> **Target Asset & Timeframe:** XAUUSD / M1

---

## 1. Executive Summary & Safety Invariants

ระบบ `QuantumTitan_V16_2_TelemetryCollector` ถูกออกแบบขึ้นเพื่อทำหน้าที่เป็น **Passive Data Collector** สำหรับงานวิจัยเชิงปริมาณ (Quantitative Research) ของโปรโตคอล V16.2 โดยมีข้อกำหนดด้านความปลอดภัยสูงสุด (Safety Invariants):

1. **Zero Trade Execution:** ปราศจากฟังก์ชันการซื้อขายทุกประเภท (`CTrade`, `OrderSend`, `PositionOpen`, `PositionClose`, `PositionModify`, `Trade.mqh` ฯลฯ)
2. **Read-Only / State Isolation:**
   * ไม่แตะต้องพอร์ตจริงหรือบัญชีทดสอบเดิม (`112334471`, `112468807`)
   * ไม่แก้ไขหรือ Overwrite EA ที่กำลังรันอยู่เดิม (`QuantumTitan_v16*`, `v21*`, `v22*`)
   * ไม่มีการต่อ Network ภายนอก (`WebRequest`) และไม่มีการใช้ Hardcoded Credentials
3. **Dedicated Output Sandbox:** บันทึกข้อมูลลงโฟลเดอร์แยกอิสระ `MQL5/Files/V162Research/`

---

## 2. Telemetry Architecture

### 2.1 Complete M1 Bar Detection & No Active Bar Write
* สคริปต์ตรวจจับแท่งเทียนที่จบแล้วเท่านั้น (`barTime > activeBar`)
* แท่งแรกสุดที่ Attach เข้าชาร์ตจะถูกตัดทิ้งเป็น Partial Bar เสมอ (`eligible = false`)
* ฟังก์ชัน `OnDeinit` มีหน้าที่เพียงสั่ง `EventKillTimer()` จะไม่มีการ Flush หรือบันทึกแท่งที่ยังไม่จบลงดิสก์

### 2.2 15-Bar FIFO Pending Queue & INVALID_GAP Isolation
```
Bar Close (t)  ──► คำนวณ Features (t <= 0) ──► Push เข้า Queue (futureCount = 0)
                          │
                          ▼ (รอเวลาผ่านไป 15 แท่ง)
Bar Close (t+15) ──► ตรวจสอบ Timestamp ครบ 15 นาทีต่อเนื่องหรือไม่?
                          ├── มี Gap / นาทีขาดหาย ──► label_status = "INVALID_GAP", ret5 = 0, ret15 = 0
                          └── ครบต่อเนื่องเป๊ะ    ──► label_status = "COMPLETE", คำนวณ ret5, ret15
                          │
                          ▼
                     Append ลง CSV วันที่ (t) แบบครั้งเดียวจบ (Append-Only)
```

### 2.3 Mandatory Python Pipeline Filtering Rule
ในไปป์ไลน์ Machine Learning / Feature Analysis ฝั่ง Python ต้องบังคับตัดแถวที่มี Gap ออกเสมอ:
```python
# กรองข้อมูลเอาเฉพาะแถวที่สมบูรณ์ 100% เท่านั้น
df = df[df["label_status"] == "COMPLETE"]
```

---

## 3. Mathematical Specifications & Dynamic DST

### 3.1 Kaufman Efficiency Ratio (KER)
คำนวณ 4 คาบเวลา $n \in \{10, 15, 20, 30\}$:
$$\text{KER}_n = \frac{|\text{Close}_t - \text{Close}_{t-n}|}{\sum_{i=1}^{n} |\text{Close}_{t - i + 1} - \text{Close}_{t - i}|}$$

### 3.2 Dynamic Measured Server Offset & Time Diagnostics
ระบบบันทึกเวลา 3 แกนเพื่อป้องกันปัญหา Timezone บน VM:
* `broker_time_epoch`, `broker_time_iso`: เวลาฝั่ง Trade Server
* `gmt_time_epoch`, `gmt_time_iso`: เวลาสากลจาก `TimeGMT()`
* `offset_seconds`, `server_utc_offset_hours`: ความต่างจริงระหว่าง Server กับ GMT

### 3.3 Dynamic UTC-Anchored Sessions & TV-VWAP
Sessions ถูกคำนวณใน **พิกัดเวลา UTC** แบบเดียวกับ TV-VWAP:
* **London Open:** 07:00 UTC (UK Summer) / 08:00 UTC (UK Winter)
* **NY Cash Open:** 13:30 UTC (US Summer) / 14:30 UTC (US Winter)
* **London Close:** 15:30 UTC (UK Summer) / 16:30 UTC (UK Winter)
* **NY Cash Close:** 20:00 UTC (US Summer) / 21:00 UTC (US Winter)
* *การแบ่ง Session:* `ASIA` $\rightarrow$ `LONDON` $\rightarrow$ `OVERLAP_LDN_NY` $\rightarrow$ `NY` $\rightarrow$ `ROLLOVER`

---

## 4. File Schemas & Structures

### 4.1 Daily Bar Telemetry File: `V162Telemetry_XAUUSD_M1_YYYYMMDD.csv` (29 คอลัมน์)
```csv
schema_version,collector_version,run_id,symbol,time_broker_epoch,time_broker_iso,server_hour,dst_session_label,open,high,low,close,tick_volume,bid,ask,spread_points,ker_10,ker_15,ker_20,ker_30,anchored_vwap_london,anchored_vwap_ny,dist_to_vwap_london,dist_to_vwap_ny,atr,quality_flags,return_after_5_bars,return_after_15_bars,label_status
```

### 4.2 Periodic Health Telemetry File: `V162Telemetry_health_YYYYMMDD.csv` (18 คอลัมน์)
```csv
schema_version,collector_version,run_id,broker_time_epoch,broker_time_iso,gmt_time_epoch,gmt_time_iso,offset_seconds,server_utc_offset_hours,terminal_connected,symbol_synchronized,last_tick_age_seconds,last_closed_bar_epoch,rows_written,duplicate_skips,gap_count,write_errors,status
```
*   `status` คงค่าเป็น `"HEALTHY"` บริสุทธิ์ (หรือรหัสข้อผิดพลาดเดี่ยว) ปราศจากการแต่งสตริงต่อท้าย
*   ข้อมูล Offset ถูกจัดเก็บในคอลัมน์เฉพาะ: `offset_seconds` และ `server_utc_offset_hours`

---

## 5. Verification & Validation Evidence

### 5.1 MetaEditor 64-Bit Compilation
* **Target:** `QuantumTitan_V16_2_TelemetryCollector.mq5`
* **Result:** 0 errors, 0 warnings (cpu='X64 Regular')
* **Binary:** `QuantumTitan_V16_2_TelemetryCollector.ex5`

### 5.2 Test Suite Execution
* **V16.2 Telemetry Test Suite (`tests/test_v16_2_telemetry.py`):**
  * Ran **14 tests in 0.051s - OK** (ผ่าน 100%)
* **Full Repository Test Suite (`python -m unittest discover -s tests`):**
  * Ran **110 tests in 0.687s - OK** (ผ่าน 100% ครบทุกระบบย่อย)
