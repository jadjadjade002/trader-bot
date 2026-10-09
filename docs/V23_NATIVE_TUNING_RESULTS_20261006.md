# ผลเปรียบเทียบ V23 และจูน config วันที่ 2026-10-06

## สรุป

รัน native MT5 real ticks ครบ 5 เดือนปฏิทินล่าสุดที่จบแล้ว: 2026-05-01 ถึง 2026-09-30 ไม่ใช่ช่วงเลื่อน May6-Oct6 ส่วนผลต้นเดือน October ไม่อยู่ในการเปรียบเทียบนี้

เปรียบเทียบ 3 รุ่น แล้วจูน 36 configs ต่อรุ่น รวม108 configs เต็ม5เดือน ทดสอบซ้ำ108 passes เฉพาะช่วงพัฒนา May-July และ replay คะแนนสูงสุดของแต่ละรุ่นที่ทุน $10,000 กับ $70 อีก6รอบ เก็บผล setup ที่ล้มเหลวแยกจากผลกลยุทธ์

ยังไม่มี config กำไรสุทธิเป็นบวกในกริดนี้ 0/108 รุ่นเสนอใหม่ลดการขาดทุน แต่ยังไม่ใช่บอทมีกำไร ไม่ deploy

| รุ่น | Net ก่อนจูน USD | Net สูงสุดในกริด USD | SL ATR | TP R | BE R |
|---|---:|---:|---:|---:|---:|
| VM ปัจจุบัน Fade=true | -1,342.34 | -952.92 | 1.0 | 3.0 | ปิด |
| ปรับ invert เป็นปกติ Fade=false | -1,221.67 | -1,087.22 | 1.0 | 3.0 | ปิด |
| รุ่นเสนอใหม่ | -341.72 | -165.23 | 1.5 | 2.0 | ปิด |

ตัวเลขตาราง: ทุนทดสอบ $10,000 เพื่อให้ระบบอยู่ครบช่วงทดลอง ไม่ใช่ขาดทุนของบัญชี VM จริง Lotคงที่0.01, leverageอ้างอิง1:200, delay200ms, MetaQuotes-Demo ไม่ใช่หลักฐาน execution ของ XM

## ข้อค้นพบ

1. สลับ Buy/Sell กลับปกติอย่างเดียวไม่ทำให้กำไร
2. รุ่นเสนอใช้ trend จาก M5 ปิดแล้ว, M1 EMA9 pullback/reclaim, EMA20 alignment, กรอง spread/ATR และไม่ไล่ราคา ไม่ใช่แค่ขยับ TP/SL ของสัญญาณเดิม
3. รุ่นเสนอที่คะแนนสูงสุด SL1.5ATR/TP2R/BEปิด ยังขาดทุน -$165.23 จาก1,476 positions NetPF0.9619 NativeequityDD4.64% จึงไม่ผ่าน
4. ที่ SL1.5ATR/TP2R เดียวกัน BE0.8R ทำให้รุ่นเสนอ netเป็น -$319.48 ส่วน BE1.2Rเป็น -$341.72 เทียบกับปิดBE -$165.23 การเพิ่ม BE ไม่ช่วยพอร์ตในชุดนี้ และเปลี่ยนลำดับไม้ถัดไปด้วย
5. รุ่นเสนอที่คะแนนสูงสุด May -$211.46, June -$156.70, July +$69.16, August +$53.03, September +$80.74 ห้ามเลือกเฉพาะ3เดือนบวกแล้วสรุปว่าชนะสม่ำเสมอ
6. ชุดทุน $70 ของค่าคะแนนสูงสุด: VM/normal เหลือ$24.42, รุ่นเสนอเหลือ$27.77 ทั้ง3ไม่มี broker stopout แต่พบ margin gate บล็อกการเปิดไม้จำนวนมาก บัญชีไม่แตกไม่ได้แปลว่ากลยุทธ์กำไร
7. Configคะแนนสูงสุดเลือกจากทั้ง5เดือน เป็น in-sample descriptive maximum ไม่ใช่ค่าที่ดีที่สุดในอนาคต ไม่มีชุดไหนผ่าน development screen จึงไม่มี candidate ที่สมควรส่งไป validation/confirmation ตามกติกา

## หลักฐานตรวจสอบ

- SSH read-only ยืนยัน EA บน VM เป็น AegisPredator_v23 และ source/binary ตรง local ไม่มีการ restart หรือแก้บัญชี
- ต้นฉบับ EX5 เทียบ harness ตรงทั้งลำดับ native orders/deals และ7 metrics รวม DD, ticks, bars
- Full comparison: 58,118,739 ticks,143,336 bars,100% real ticks
- Optimization216 rows ตรวจตรง native XML ทุก pass ทั้ง parameter, net, trade count, DD
- Replayคะแนนสูงสุดแต่ละรุ่น net/trade count ตรง optimization
- Net รวม profit+commission+swap+fee จัดกลุ่มตามposition ID ไม่ใช่นับdealซ้ำ
- Tick-cache May-Sep SHA-256 ตรงหลักฐานเดิม ไม่เปลี่ยนระหว่าง supplemental retests
- Breakerคงเดิม ไม่มีการแก้ตามคำสั่งผู้ใช้
- Compile0errors0warnings, focusedpytest35passedและ3subtestspassed Fullsuite collectionติด2EAlegacyที่ไม่มีไฟล์ ไม่แก้ไฟล์นอกขอบเขต

## ขั้นถัดไปที่หลักฐานรองรับ

อย่าจูน TP/BE ต่อแบบสุ่มเพื่อให้ช่วงเดิมบวก ต้องหาข้อมูลเข้าไม้ที่เพิ่ม edge จริง ตั้งสมมติฐานก่อนทดสอบ เช่น แยก market regime และตรวจ directional markout หลัง spread โดยใช้ closed-bar features ที่รู้ได้ก่อนเข้า จากนั้นแยกทดสอบทีละเงื่อนไขและเก็บช่วงอนาคตไว้ไม่ดูผลล่วงหน้า ยังไม่ดำเนินการสมมติฐานใหม่หรือ deploy ในรอบนี้

รายงานละเอียดและ native evidence อยู่ที่:

- [รายงานทั้งหมด](../reports/v23_tuning_20261006/complete5m_batch1_report.md)
- [ผล machine-readable](../reports/v23_tuning_20261006/complete5m_batch1_analysis.json)
- [Independent evidence audit](../reports/v23_tuning_20261006/complete5m_batch1_evidence_audit.json)
- [Protocol](V23_NATIVE_TUNING_PROTOCOL_20261006.md)

ใช้ skill spreadsheets ตรวจหน่วย จำนวนแถว การจับคู่ pass และยอดรวม ไม่สร้างหรือเปลี่ยน workbook เพิ่ม
