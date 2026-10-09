# ทำไมบาง config ชนะ และควรพัฒนาอะไรต่อ

วันที่ 2026-10-08. วิเคราะห์ evidence เดิมและ actual native trade ledgers. ไม่ใช่ผล backtest ใหม่ของบอทที่แก้แล้ว. ยังไม่มี qualified V25 และไม่มีการเปลี่ยนบอทบน VM.

## คำตอบหลัก

มีสองกลไกทำเงินต่างกันในชุดทดลอง:

1. Continuation / reclaim ใช้การยืนยันทิศและยอมให้ไม้ชนะวิ่งไกล. Win rate ต่ำ แต่กำไรเฉลี่ยของไม้ชนะใหญ่กว่าไม้แพ้.
2. Exhaustion ใช้การกลับยืน EMA หลังเคลื่อนสวนเทรนด์ M5. ในตัวอย่างที่จับคู่ได้ครบ การเก็บกำไร 1R แทน 2R ทำให้ไม้ที่เคยกลับไปจบ SL กลายเป็น TP มากขึ้น.

ตัวเลขสนับสนุนผลที่เกิดขึ้นจริงในตัวอย่าง ไม่ได้พิสูจน์ว่ารูปแบบราคานี้ทำนายอนาคตได้สม่ำเสมอ. ปัจจัยเสี่ยงอีกชุดคือ spread / quote หลังช่วงขาดราคา ซึ่งการทายทิศถูกอย่างเดียวป้องกันไม่ได้.

## 1. ขอบเขตข้อมูล

- 140 development configs จาก 11 กลุ่ม entry rules. บวก 50 configs ลบ 90 configs. ไม่ใช่ 140 กลยุทธ์อิสระ.
- Development: `[2025-12-01, 2026-06-01)` ตาม clock label ของ broker/tester. Validation: June และ July 2026.
- บางตัวมี diagnostic replay 10 เดือน `[2025-12-01, 2026-10-01)`. ไม่ใช่ทุก config ครบ 10 เดือน.
- XAUUSD M1, MetaQuotes-Demo real ticks, delay 200ms, ทุนทดสอบ $10,000, 0.01 lot คงที่, leverage 1:200. ไม่ใช่ผลทุน $70 หรือ broker XM.
- ใช้ profit + commission + swap + fee รวมตาม position ID. Bid/Ask ฝังในราคา fill แล้ว ไม่หัก spread ซ้ำ.
- BE ปิดทุกตัวในชุดนี้. จึงยังสรุปจากชุดนี้ไม่ได้ว่าเปลี่ยนเวลา BE แล้วช่วยเท่าไร.

## 2. Continuation ที่กำไรสูงสุดชนะด้วยขนาด payoff ไม่ใช่ win rate สูง

อ้างอิงแถว ID036 ในรายงาน 140 configs: R1 mode1, preset2, SL2ATR, TP3R.

| ตัวชี้วัด development | ค่า |
| --- | ---: |
| Positions / wins / losses | 1,797 / 539 / 1,258 |
| Net | +$808.41 |
| PF จาก grouped-net components | 1.0896 |
| Win rate | 29.99% |
| Net ของไม้ชนะรวม | $9,833.57 |
| ขาดทุนสุทธิของไม้แพ้รวม | $9,025.16 |
| กำไรสุทธิเฉลี่ยต่อไม้ชนะ | $18.2441 |
| ขาดทุนสุทธิเฉลี่ยต่อไม้แพ้ | $7.1742 |
| Win rate คุ้มทุนจากค่าเฉลี่ยที่เกิดขึ้น | 28.22% |
| กำไรเฉลี่ยต่อ position | $0.4499 |

คำนวณตรงจาก `gross_net_wins`, `gross_net_losses`, `wins`, `positions` ใน R1 accepted optimizer rows. ไม่ต้องมี per-position path เพื่อคำนวณค่าเฉลี่ยเหล่านี้. แต่ optimizer rows ไม่มีทางเดินราคา, side หรือ exit reason ของแต่ละ pass จึงห้ามแต่งสาเหตุรายไม้.

กลไก source: ใช้ M5 EMA20/50 กับ slope ที่ปิดแล้ว, M1 EMA9/20 ไปทางเดียวกัน, แท่งยืนทะลุ high/low ก่อนหน้าพร้อม buffer. Preset2 ต้อง body >=0.30ATR และ close location >=0.80. Source ปฏิเสธแท่ง range >2ATR, spread >0.1ATR และ quote ที่ห่าง signal close >0.5ATR.

Source anchors: `research/ResearchCandidate_R1.mq5:110-175`, `:644-697`, `:752-756`. สิ่งเหล่านี้อธิบายกติกาคัดเข้า ไม่ใช่หลักฐานแยกว่ากติกาข้อใดทำกำไร.

### ความสม่ำเสมอยังไม่ผ่าน

Diagnostic 10 เดือนของตัวเลือกเดียวกันได้ +$547.26, PF1.0457, 2,490 positions, native DD6.16%. V24 baseline DD5.71%. เป็นตัวเลือกจาก development เท่านั้น ไม่ได้เลือกผู้ชนะจาก full-period maximum.

January +$560.17 และ March +$525.96 เป็นกำไรรวม +$1,086.13 มากกว่ายอดทั้ง 10 เดือน. June ถึง September รวม -$261.15. กำไรบางช่วงจึงถูกคืนในช่วงอื่น.

Extra-cost accounting stress $0.20 ต่อ position เหลือ +$49.26 และ $0.50 กลายเป็น -$697.74. นี่เป็น cost sensitivity แบบคง trade set ไม่ใช่ native simulation เปลี่ยน spread.

สรุป: มี positive realized payoff แต่ขอบกำไรบางและไม่เสถียรพอเป็นรุ่น release.

## 3. TP ต้องเข้ากับกลุ่มสัญญาณ

R1 กลุ่ม continuation / reclaim / breakout: TP1R ติดลบทุก 27 cells ที่เปลี่ยน SL และ preset. สำหรับ TP3R, continuation บวก 5/9 cells และ reclaim บวก 7/9 cells.

ค่าเฉลี่ย Net ของ 9 configs ต่อกลุ่ม ไม่ใช่กำไรของ portfolio และไม่ใช่ค่า expectancy ต่อไม้:

| กลุ่ม | TP1R mean Net USD | TP2R mean Net USD | TP3R mean Net USD |
| --- | ---: | ---: | ---: |
| Continuation | -850.09 | -229.99 | -33.14 |
| Reclaim | -753.85 | -93.59 | +209.69 |
| Breakout | -432.92 | -152.45 | -47.00 |

แต่ R4 exhaustion ให้ผลดีกว่าเมื่อ TP ใกล้ขึ้นตามคู่ native replays ด้านล่าง. จึงไม่ควรนำ TP1R ไปใช้กับทุก bot. R1 grid เป็น aggregate association เพราะ exit / occupancy และ entry sets ของแต่ละ config อาจต่างกัน.

## 4. หลักฐานที่แรงที่สุด: R4 เปิดชุดเดียวกันครบ 156 positions

กลุ่ม R4 preset1 SL1.5ATR เปรียบเทียบ TP0.75 / 1 / 1.5 / 2R. ตรวจ accepted signatures พบ source SHA, binary SHA, runtime และหก monthly cache hashes เดียวกัน. Settings เหมือนกันนอกจาก TP และ RunTag.

จับคู่ข้าม replay ด้วย entry timestamp มิลลิวินาที + side + entry price + volume ไม่ใช้ position ID ข้าม replay. ทั้งสี่ชุดมี common entries 156/156 และไม่มี unmatched entries ใน sample นี้.

| TP | Wins / losses | Win % | Net USD | PF | Net ต่อ position USD |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0.75R | 93 / 63 | 59.62 | +77.27 | 1.2524 | +0.4953 |
| 1R | 81 / 75 | 51.92 | +98.82 | 1.2759 | +0.6335 |
| 1.5R | 59 / 97 | 37.82 | +38.71 | 1.0820 | +0.2481 |
| 2R | 49 / 107 | 31.41 | +7.61 | 1.0142 | +0.0488 |

เปลี่ยน 2R เป็น 1R ใน actual native replays:

- SL ที่ 2R กลายเป็น TP ที่ 1R: 32 positions.
- TP ที่ 2R ยังคงเป็น TP ที่ 1R: 48 positions.
- SL ทั้งสองชุด: 75 positions.
- Expert close ที่ 2R กลายเป็น TP ที่ 1R: 1 position.
- TP ที่ 2R กลายเป็น SL ที่ 1R: 0 positions.
- Net เพิ่มจริง +$91.21 รวมทุก position ไม่ตัดไม้แพ้.

แจกแจงผลต่างกำไรสุทธิของ entry ที่จับคู่ได้ ไม่ใช่การทำนาย exit สมมุติ:

| Exit ที่ TP2R → TP1R | Positions | Net ที่ TP2R USD | Net ที่ TP1R USD | ผลต่าง USD |
| --- | ---: | ---: | ---: | ---: |
| SL → SL | 75 | -358.19 | -358.19 | 0.00 |
| SL → TP | 32 | -178.85 | +178.61 | +357.46 |
| TP → TP | 48 | +538.99 | +274.33 | -264.66 |
| Expert close → TP | 1 | +5.66 | +4.07 | -1.59 |
| รวม | 156 | +7.61 | +98.82 | +91.21 |

เหตุผลทางเศรษฐศาสตร์ชัดขึ้น: 32 ไม้ที่เปลี่ยนจากแพ้เป็นชนะช่วย +$357.46 แต่การเก็บใกล้ขึ้นเสีย payout ของอีก 49 ไม้รวม $266.25. เหลือผลดีสุทธิ $91.21. ไม่ใช่ทุกไม้ดีขึ้น และไม่ได้แค่เพิ่ม win rate โดยไม่เสียอะไร.

นี่สนับสนุนคำอธิบายว่า target2R รอไกลเกินผลกำไรที่ realization ได้ใน exhaustion sample นี้. ใช้ actual executed ledgers ไม่ได้คาดเดา exit จาก MFE. ผลจำกัดเฉพาะช่วงและ controls ที่จับคู่ได้ ไม่ใช่คำยืนยันว่า 1R optimal หรือใช้ได้กับทุกตลาด. Exit policy ยังเปลี่ยน occupancy และ breaker state ได้ในการทดลองอื่น ต้องตรวจ entry sets ใหม่ทุกครั้ง.

### Win rate มากกว่า ไม่ได้แปลว่ากำไรมากกว่า

TP0.75 มี win rate59.62% สูงกว่า TP1 ที่51.92% แต่กำไรต่ำกว่า เพราะ payout ต่อไม้ชนะเล็กลง. ค่าเฉลี่ย native ปัดเศษ: TP0.75 ชนะ $4.12 แพ้ $4.86, TP1 ชนะ $5.64 แพ้ $4.78.

เมื่อไม่มีไม้ศูนย์ใน sample: กำไรเฉลี่ยต่อไม้ = p × average win - (1-p) × average loss. Win rate คุ้มทุน = average loss / (average win + average loss). ทั้งหมดเป็นค่าของ sample ไม่ใช่ forecast.

คำนวณจาก grouped net ที่ไม่ปัดเศษ: TP1 คุ้มทุน45.8426% แต่ observed51.9231%. มีขอบกำไร6.0805 percentage points ใน development. ถ้ามี zero-PnL trades ต้องแยก denominator ของ decisive win rate ออกจาก all-position win rate.

## 5. ทำไมยังไม่ผ่านเมื่อขยายเป็น 10 เดือน

R4 TP1 diagnostic 10 เดือน: 202 positions, win52.48%, net-$2.68, PF0.9955. Average winner จาก grouped net ประมาณ$5.55 แต่ average loser ประมาณ$6.16. จำนวนชนะมากกว่าแพ้ยังไม่พอชดเชยขนาด loss.

Position388: sell4327.48, initial SL4331.60, exit4469.17. Deal profit-$141.69, swap-$0.05, position net-$141.74. Planned price risk4.12 แต่ realized lossประมาณ34.4R. ประมาณ25.5ไม้ชนะเฉลี่ยถูกกินด้วย position นี้เพียงตัวเดียว.

Raw minute samples ก่อน gap: Bid4324.39 / Ask4324.78. หลัง gap: Bid4320.26 / Ask4469.17. Bid ลดลง แต่ Ask พุ่งและเท่าราคา exit ของ short. ไม่ใช่หลักฐานว่า sell ผิดทิศเพราะกราฟ Bid ขึ้นชน SL. ไม่พบหลักฐานแยกว่ามี execution slippage เพิ่มหลัง quote นี้ หรือว่าเป็น false feed / news.

ตาม MetaTrader หลักทั่วไป SL ของ short ตรวจด้วย Ask และของ long ตรวจด้วย Bid. อ้างอิง [MetaTrader 5 Basic Principles](https://www.metatrader5.com/en/terminal/help/trading/general_concept#stop_loss). การอธิบายกลไกของเครื่องมือไม่ยืนยันความถูกต้องของ feed ที่ใช้ทดลอง.

ห้ามลบ position388 หรือหัก loss ออกแล้วเรียกว่าบอทแก้สำเร็จ. ต้องเขียน policy ใหม่และ native replay ซึ่งจะเปลี่ยนทั้ง missed winners และ future entries.

## 6. พบความต่างของทิศ M1 กับ M5 ใน source จริง

R4 `ReadR2Context` อ่าน M5 EMA20/50 และ slope เพื่อกำหนด direction. อ่าน M1 EMA9/20 ด้วย แต่ `CandidateR2Signal` บังคับ `R2M1Aligned` เฉพาะ modes1,2,4 ไม่บังคับ mode5 exhaustion.

Anchors: `research/ResearchCandidate_R4.mq5:147-162`, `:358-363`, `:382-385`. R2 ต้นฉบับมีโครงสร้างเดียวกันที่`:139-154`, `:350-355`, `:374-377`.

ดังนั้น mode5 อาจเปิดตาม M5 แต่สวนบริบท M1 EMA9/20 ได้. เป็นคุณสมบัติกติกาปัจจุบัน ไม่ใช่ข้อพิสูจน์ว่าเป็น bug และไม่ใช่ข้อพิสูจน์ว่าการกรองเพิ่มจะช่วย. การรอ M1 aligned อาจตัด early reversal ที่ชนะออกด้วย.

สัญญาณ exhaustion จริง: ต้องเคลื่อนสวน M5 อย่างน้อย1.25ATR สำหรับ preset0 หรือ1.75ATR สำหรับ preset1, ทดสอบ prior extreme, ปิดแท่งกลับข้าม EMA9 และ close locationอย่างน้อย0.70. `R2TrendCandle` ไม่ได้มี minimum body/ATR โดยเฉพาะ. ห้ามอ้างว่ามี body guard แบบ R1 ทั้งที่ source ไม่ได้ทำ.

## 7. ความเสถียรและข้อห้ามในการอนุมาน

- R4 TP1 development บวก4/6เดือน. Jan+Feb รวม+$120.88 มากกว่า total+$98.82. ไม่ใช่กำไรทุกเดือน.
- สอง R4 validation configs มีเพียง28positions ต่ำกว่า frozen floor40. PFบวกไม่พอเป็น locked finalist.
- R3 PF6.1237 จาก4positionsใน10เดือน ไม่ใช่หลักฐานว่าดีกว่า.
- R1สิบเดือน BUY-$11.04 / SELL+$558.30 แต่ R4สิบเดือน BUY+$20.62 / SELL-$23.30. ไม่สนับสนุนการปิด BUY ทั้งระบบหรือ invert สัญญาณทั้งระบบ.
- แท่งชนะและ context ที่เห็นหลังเกิดผล อาจเป็น selection bias. ต้องใช้ completed features ก่อน entry และ prospective freeze.
- MAE/MFE เป็น callback-sampled extrema ไม่ใช่ทุก raw tick. ไม่รู้ first-hit ordering ของ exit สมมุติทั้งหมด. มี timestamp anomaly ใน R2 path samples ที่บันทึกก่อน entry deal200ms ต้องเปิดเผย.
- June ถึง September เคยถูกตรวจแล้ว. ผล historical replay ใหม่ยังเป็น retrospective ไม่ใช่ untouched OOS.

## 8. ทางพัฒนาต่อที่ล็อกไว้

เลือก exhaustion เป็นกลุ่มทดลองเฉพาะ เพราะจับคู่ native exits ได้ และมี entry-context hypothesis ที่ตรวจได้. ไม่รวมหลายกลยุทธ์ ไม่เพิ่ม grid / martingale ไม่ invert ไม่แก้ breaker ในรอบนี้.

1. เพิ่ม diagnostic features ก่อน entry: closed M1 EMA9/20, closed M5 EMA20/50, M5 slope, ATR, prior displacement, close location, actual spread และ session time-to-close. ตรวจทั้งไม้เข้าและ signals ที่ถูกปฏิเสธ.
2. ทดลอง M1 alignment off/on ด้วย predicateเดิมที่ sourceมีอยู่: BUYต้องEMA9>EMA20, SELLต้องEMA9<EMA20 ใช้ shift1เท่านั้น. ไม่เพิ่มอินดิเคเตอร์หลายตัวพร้อมกัน.
3. ทดลอง closure policy off/on: block entry และ flatten ก่อน broker session end. Entry-only spread guard ป้องกันไม้ที่ถืออยู่ผ่าน no-quote intervalไม่ได้.
4. แยก2ปัจจัยแบบ2×2 และทดสอบ preset0/1 รวม8configs. Fix SL1.5ATR, TP1R, BEoff, lot0.01, delay200ms และ breakerเดิม. TP1 เป็น research setting ไม่ใช่ค่าที่รับประกันดีที่สุด.
5. ต้องยืนยัน schedule / clock ก่อนเปิด closure-policy arms. `SymbolInfoSessionTrade` รับ sessions ต่อ day-of-week แต่ไม่มี historical-date argument จึงห้ามถือ current metadata เป็นหลักฐานตารางย้อนหลัง. อ้างอิง [MQL5 Reference](https://www.mql5.com/en/docs/marketinformation/symbolinfosessiontrade).
6. คง gates เดิม. Development positive / PF>=1.20 / N>=150, validation positive / PF>=1.20 / N>=40. ไม่ลด floor เพื่อให้ filter ที่เปิดน้อยดูผ่าน.
7. Lock candidate ก่อน confirmation. Native10เดือน, cost sensitivity, 500ms และทุน$70 เป็นคนละการตรวจ. Future dataเริ่มหลัง source/settings lockจริง ไม่เรียก Octoberย้อนหลังที่เปิดดูแล้วว่าunseen.

รายละเอียดเงื่อนไขก่อนรันและ matrix อยู่ `docs/CANDIDATE_R5_EXPERIMENT_PLAN_20261008.md`. รอบนี้สร้างตัววิเคราะห์และแผน ยังไม่สร้าง/compile/deploy R5 EA และยังไม่ตั้งชื่อ V25.

## 9. หลักฐานและการทำซ้ำ

- `reports/v25_research_20261007/r1_b_complete.json`
- `reports/v25_research_20261007/r2_a_complete.json`
- `reports/v25_research_20261007/r3_a_complete.json`
- `reports/v25_research_20261007/r4_a_complete.json`
- `reports/v25_research_20261007/runs/r4_a_dev_5_1_sl1p5_tp0p75/`
- `reports/v25_research_20261007/runs/r4_a_dev_5_1_sl1p5_tp1p0/`
- `reports/v25_research_20261007/runs/r4_a_dev_5_1_sl1p5_tp1p5/`
- `reports/v25_research_20261007/runs/r4_a_dev_5_1_sl1p5_tp2p0/`
- `reports/v25_research_20261007/runs/r4_a_descriptive10m/`
- `docs/CANDIDATE_R2_EXHAUSTION_DIAGNOSTIC.md`
- `docs/CANDIDATE_R4_GAP_DIAGNOSTIC.md`
- `docs/CANDIDATE_140_CONFIG_RESULTS_20261008.md`

Three Luna workers supplied source mechanics, native exit matching and validation review. Orchestrator independently checked the156-entry2R→1R pair, +$91.21 delta, transition counts, source M1 alignment scope and R1 payoff math. Source-review errors were corrected before accepting this report. No external-model debate claimed.

## 10. ตัววิเคราะห์ที่ตรวจผ่านแล้ว

สร้าง `research/candidate_winner_attribution.py` และ `tests/test_candidate_winner_attribution.py`. ผล JSON ที่รันจริงและตรวจซ้ำอยู่ `reports/v25_research_20261007/winner_attribution_20261008.json`.

- Unit tests ใหม่ 19/19 ผ่าน. รวม regression ที่เกี่ยวข้องอีก 50 tests เป็น 69/69 ผ่าน. ไม่ใช่คำกล่าวว่าทั้ง repository ผ่านทุก test.
- CLI รันกับ native evidence เดิมสำเร็จ. ยืนยัน TP0.75/1/1.5/2R net เท่ากับ $77.27/$98.82/$38.71/$7.61 และคู่ TP2R→1R มี 156 common, unmatched0, delta+$91.21.
- ตรวจ source/binary identity, runtime hashes, cache ทั้งหก development เดือนและสิบ diagnostic เดือน รวม identity ของเดือนที่ทับกัน.
- อ่าน `.set` UTF-16 หรือ UTF-8 แบบ strict. ตรวจ settings ครบและ normalized SET digest ตาม convention ของ runner ไม่เรียกว่า raw-byte hash.
- Reconcile native HTML, accepted report, deals, position count, capital, leverage, net, final balance และ native DD. คิด cost stress ใหม่จาก ledger.
- Reject เวลา/ตัวเลขผิด, settings ขาด, identity ต่าง, foreign deals, partial exits และ cash adjustments. ไม่สร้าง settings หรือ PnL แทนค่าที่หาย.
- จับคู่ entry จริงด้วย timestamp มิลลิวินาที, side, price และ volume. แยก transition count กับ transition economics. Unmatched entries ยังอยู่ใน total delta แต่ไม่แต่ง outcome.
- Win rate และ break-even ระบุ denominator ชัด. Zero-PnL ไม่ถูกนับเป็น winner หรือใช้กลบ loss.
- Luna ตรวจ implementation แยกจากผู้เขียน. Orchestrator รัน tests และ CLI ซ้ำ ตรวจ source/binary hashes และ transition economics เอง.

รันซ้ำจาก project root:

```powershell
python research/candidate_winner_attribution.py
python -m unittest tests.test_candidate_winner_attribution -v
python -m unittest tests.test_candidate_winner_attribution tests.test_candidate_exhaustion_diagnostic tests.test_candidate_r4 tests.test_candidate_r4_runner tests.test_candidate_r4_luna_review tests.test_candidate_release_evidence tests.test_candidate_r1_runner tests.test_candidate_r1_luna_review
```

รอบตรวจนี้ใช้ bundled Python ที่ `C:/Users/USER/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`. Script SHA256: `86147D7A74D365947C164BBD2323D4FA50FA617989EE877A899B9B3EC1E66727`.

สถานะสุดท้าย: analysis และ diagnostic tool เสร็จ. R5 matrix ยัง PRE-IMPLEMENTATION. ไม่ใช่ backtest ใหม่, ไม่ compile EA, ไม่เปลี่ยน VM/accounts, ไม่ commit/push และยังไม่มี qualified V25.
