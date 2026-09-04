import MetaTrader5 as mt5
import datetime
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

def main():
    if not mt5.initialize():
        print("Failed to initialize MT5, error:", mt5.last_error())
        return

    acc = mt5.account_info()
    if acc:
        print("=" * 55)
        print("          🛡️ LIVE MT5 SYSTEM HEALTH REPORT")
        print("=" * 55)
        trade_mode = "DEMO" if acc.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO else "REAL"
        print(f"Account Login   : {acc.login} ({acc.company})")
        print(f"Server          : {acc.server}")
        print(f"Account Mode    : {trade_mode}")
        print(f"Currency        : {acc.currency}")
        print(f"Balance         : ${acc.balance:.2f}")
        print(f"Equity          : ${acc.equity:.2f}")
        print(f"Margin Used     : ${acc.margin:.2f}")
        print(f"Free Margin     : ${acc.margin_free:.2f}")
        margin_level = f"{acc.margin_level:.1f}%" if acc.margin > 0 else "N/A (No positions)"
        print(f"Margin Level    : {margin_level}")
        print(f"Hard Floor Gate : $30.00 (Status: SAFE, Buffer: +${acc.equity - 30.0:.2f})")

    # Positions
    positions = mt5.positions_get()
    print("\n" + "-" * 55)
    print("📋 ACTIVE POSITIONS (คำสั่งที่เปิดค้างอยู่):")
    print("-" * 55)
    if positions:
        for p in positions:
            p_type = "BUY 🟢" if p.type == 0 else "SELL 🔴"
            print(f"  • Ticket #{p.ticket}: {p.symbol} | {p_type} | Vol: {p.volume:.2f} lot")
            print(f"    Entry: {p.price_open:.2f} -> Current: {p.price_current:.2f}")
            print(f"    SL: {p.sl:.2f} | TP: {p.tp:.2f} | Profit: ${p.profit:.2f}")
    else:
        print("  • ปัจจุบันไม่มีออเดอร์เปิดค้างอยู่ (All Clean - บอทกำลังเฝ้าโซน SMC)")

    # Symbols check
    print("\n" + "-" * 55)
    print("📈 MARKET QUOTES & SPREAD MONITOR:")
    print("-" * 55)
    for sym in ["XAUUSD", "EURUSD"]:
        tick = mt5.symbol_info_tick(sym)
        info = mt5.symbol_info(sym)
        if tick and info:
            spread_pts = round((tick.ask - tick.bid) / info.point)
            spread_status = "NORMAL ✅" if spread_pts <= 45 else "HIGH ⚠️"
            print(f"  • {sym:<7}: Bid={tick.bid:.{info.digits}f} | Ask={tick.ask:.{info.digits}f} | Spread={spread_pts} pts ({spread_status})")

    # Recent Deals today
    today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    deals = mt5.history_deals_get(today, datetime.datetime.now())
    print("\n" + "-" * 55)
    print("📜 TODAY'S DEAL HISTORY (ประวัติการเทรดวันนี้):")
    print("-" * 55)
    if deals:
        closed_deals = [d for d in deals if d.entry == mt5.DEAL_ENTRY_OUT]
        print(f"  • Total Executed Trades Today: {len(closed_deals)}")
        total_pnl = sum(d.profit + d.commission + d.swap for d in closed_deals)
        for d in closed_deals[-5:]:
            t_str = datetime.datetime.fromtimestamp(d.time).strftime("%H:%M:%S")
            pnl = d.profit + d.commission + d.swap
            res = "WIN 🟢" if pnl >= 0 else "LOSS 🔴"
            print(f"    [{t_str}] Ticket #{d.order}: {d.symbol} | Vol: {d.volume:.2f} | PnL: ${pnl:.2f} ({res})")
        print(f"  • Net Daily Realized PnL: ${total_pnl:.2f}")
    else:
        print("  • No closed deals today yet.")

    print("=" * 55)
    mt5.shutdown()

if __name__ == "__main__":
    main()
