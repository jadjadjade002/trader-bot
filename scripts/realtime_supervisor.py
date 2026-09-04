import MetaTrader5 as mt5
import time
import datetime
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

def log(msg):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{now}] {msg}"
    print(line, flush=True)
    with open("d:\\project\\trader-bot\\supervisor.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")

def main():
    log("🚀 Realtime Institutional Quant Supervisor Started.")
    if not mt5.initialize():
        log(f"❌ Failed to initialize MT5: {mt5.last_error()}")
        return

    acc = mt5.account_info()
    if not acc:
        log("❌ Cannot retrieve account info.")
        mt5.shutdown()
        return

    log(f"✅ Connected to Account #{acc.login} ({acc.server}) | Balance: ${acc.balance:.2f} | Equity: ${acc.equity:.2f}")

    last_report_time = 0
    last_positions_count = -1

    while True:
        try:
            acc = mt5.account_info()
            if not acc:
                log("⚠️ Reconnecting to MT5...")
                mt5.initialize()
                time.sleep(5)
                continue

            # Hard Equity Floor Check
            if acc.equity < 30.0:
                log(f"🚨 CRITICAL: Equity fell below hard floor ($30.00)! Current: ${acc.equity:.2f}")

            positions = mt5.positions_get()
            pos_count = len(positions) if positions else 0

            # Detect position change
            if pos_count != last_positions_count:
                if pos_count > 0:
                    for p in positions:
                        p_type = "BUY 🟢" if p.type == 0 else "SELL 🔴"
                        log(f"⚡ ACTIVE POSITION: Ticket #{p.ticket} | {p.symbol} | {p_type} | Vol: {p.volume:.2f} | Entry: {p.price_open:.2f} | Current: {p.price_current:.2f} | PnL: ${p.profit:.2f}")
                else:
                    log("ℹ️ All positions closed. Market scanning in progress.")
                last_positions_count = pos_count

            # Periodic Heartbeat every 60 seconds
            now_ts = time.time()
            if now_ts - last_report_time >= 60:
                spread_xau = "N/A"
                tick = mt5.symbol_info_tick("XAUUSD")
                if tick:
                    spread_pts = round((tick.ask - tick.bid) / 0.01)
                    spread_xau = f"{spread_pts} pts"

                log(f"💓 Heartbeat: Eq=${acc.equity:.2f} | Bal=${acc.balance:.2f} | Open={pos_count} | XAU Spread={spread_xau}")
                last_report_time = now_ts

            time.sleep(5)
        except Exception as e:
            log(f"⚠️ Supervisor exception: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
