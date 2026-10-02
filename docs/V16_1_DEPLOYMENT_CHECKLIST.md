# QuantumTitan V16.1 M1 Deployment Checklist

**Target Account**: `112468807` (Authorized Demo Account)  
**Protected Account**: `112334471` (V16 Live Baseline - STRICT PROHIBITION)  
**Target Symbol & Timeframe**: `XAUUSD, M1`  
**EA Name**: `QuantumTitan_v16_1_M1`  
**Magic Number**: `991612`  

---

## Pre-Deployment Verification Gates

Before deploying or attaching `QuantumTitan_v16_1_M1.ex5` to any chart, ALL gates below must be confirmed:

- [x] **Gate 1: Account Confirmation**
  - Verify terminal login is strictly `112468807`. (VERIFIED: Authorized on MetaQuotes-Demo)
  - Verify account trade mode is `DEMO`. (VERIFIED: Demo account - hedging mode)
  - Verify account is NOT `112334471`. (VERIFIED)
- [x] **Gate 2: Terminal & Data Isolation**
  - Must run on a separate MT5 portable instance or separate data directory from the V16 instance. (VERIFIED: `/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5 v16_1`)
  - Navigator active account must be verified from Terminal Journal: `Account: 112468807 (Demo)`. (VERIFIED: Log PID 157870)
- [x] **Gate 3: Binary Compilation & Integrity**
  - Compiled binary `QuantumTitan_v16_1_M1.ex5` exists with 0 errors and 0 warnings. (VERIFIED)
  - SHA-256 matches: `8331BE27AC43BD8CD5E099E60A809FE733CDE265F8C2564E32DC565E69A2342A`. (VERIFIED)
- [x] **Gate 4: Chart Setup**
  - Symbol: `XAUUSD` (VERIFIED)
  - Period: `M1` (1 Minute) (VERIFIED)
  - No other EA attached to this chart window. (VERIFIED)
- [x] **Gate 5: Input Parameter Verification**
  - `InpDemoOnly` = `true` (VERIFIED)
  - `InpMagicNumber` = `991612` (VERIFIED)
  - `InpBaseLot` = `0.01` (VERIFIED)
  - `InpTakeProfitPoints` = `260.0` (VERIFIED)
  - `InpStopLossPoints` = `260.0` (VERIFIED)
  - `InpBreakevenTriggerPts` = `130.0` (VERIFIED)
  - `InpBreakevenLockPts` = `20.0` (VERIFIED)
  - `InpMaxSpreadPoints` = `35.0` (VERIFIED)
  - `InpCooldownBars` = `3` (VERIFIED)
  - `InpMinAtrPoints` = `80.0` (VERIFIED)
  - `InpMinConfidenceScore` = `70` (VERIFIED)
  - `InpEnableHUD` = `true` (VERIFIED)
- [x] **Gate 6: Algo Trading Status**
  - MT5 Algo Trading enabled in common.ini (`Enabled=1`, `AllowLiveTrading=1`). (VERIFIED)
- [x] **Gate 7: Baseline Protection Check**
  - Verify account `112334471` on the VM is still active, positions and charts untouched. (VERIFIED: PID 100324 running continuously)

---

## Post-Deployment Read-Only Inspection Checklist (Completed & Verified)

1. **Terminal Journal Initialization**:
   - `01:46:28.610 Network '112468807': authorized on MetaQuotes-Demo through Access Point EU 0`
   - `01:46:32.369 Network '112468807': trading has been enabled, demo account - hedging mode`
   - `01:46:32.514 QuantumTitan_v16_1_M1 (XAUUSD,M1) ⚡ QuantumTitan v16.10 M1 Initialized on XAUUSD M1 (Magic: 991612 | TP: +260 pts | BE: +130 pts)`
2. **First Organic Signal & Trade Execution**:
   - `01:47:00.945 QuantumTitan_v16_1_M1 (XAUUSD,M1) ⚡ [V16.1 M1] SELL SCALP OPENED @ 4325.56000 | Score: 85/100 | SL: 4328.16000 (-260 pts) | TP: 4322.96000 (+260 pts) | Lot: 0.01 | Spread: 34.0 pts`
3. **Isolation Verification**:
   - V16 baseline running in `/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5` (PID 100324 on account `112334471`) untouched and unaffected.
   - V16.1 running in `/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5 v16_1` (PID 157870 on account `112468807`).

---

## Emergency Rollback Procedure

If any unexpected condition occurs (account mismatch, unexpected order size, duplicate magic, abnormal CPU usage, broker reject loop):

1. **Step 1**: Immediately click the red "Algo Trading" button in the MT5 top toolbar of account `112468807` to freeze execution.
2. **Step 2**: Remove the EA by right-clicking chart $\rightarrow$ Expert List $\rightarrow$ Remove `QuantumTitan_v16_1_M1`.
3. **Step 3**: If any unauthorized position was opened, close it manually or via MT5 Terminal Toolbox.
4. **Step 4**: DO NOT touch, close, or restart the terminal of account `112334471`.
5. **Step 5**: Save the MT5 Journal log (`/MQL5/Logs/`) and report the incident (Ticket, Magic, Symbol, RetCode, Timestamp).
6. **Step 6**: Investigate root cause before re-attaching.
