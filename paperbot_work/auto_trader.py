#!/usr/bin/env python3
"""Orochi scheduled Alpaca paper auto-trader.

Run once per invocation (for hosted cron) or continuously on a machine.
All broker clients are created with paper=True in engine.data.
"""
import os
import sys
import time
import argparse
from datetime import datetime
import pytz

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv
load_dotenv()

from engine.strategy import run_daily_scan
from engine.data import get_account, get_positions, get_bars, close_position
from engine.indicators import add_indicators
from engine.quant import check_daily_loss_limit, portfolio_heat

ET = pytz.timezone("America/New_York")
RUN_AFTER_HOUR, RUN_AFTER_MINUTE = 9, 45
RUN_BEFORE_HOUR = 15
CHECK_INTERVAL = 60


def log(message):
    print(f"[{datetime.now(ET):%Y-%m-%d %H:%M:%S %Z}] {message}", flush=True)


def in_run_window():
    now = datetime.now(ET)
    start = now.replace(hour=RUN_AFTER_HOUR, minute=RUN_AFTER_MINUTE, second=0, microsecond=0)
    end = now.replace(hour=RUN_BEFORE_HOUR, minute=0, second=0, microsecond=0)
    return now.weekday() < 5 and start <= now <= end


def manage_exits():
    """Monitor existing longs and close at 1.4 ATR loss or 2.8 ATR gain."""
    for symbol, position in get_positions().items():
        if float(position.qty) <= 0:
            continue
        bars = get_bars(symbol, "5Min", limit=80)
        if bars.empty:
            log(f"EXIT CHECK SKIPPED {symbol}: no recent bars")
            continue
        frame = add_indicators(bars)
        if "atr" not in frame or frame["atr"].dropna().empty:
            log(f"EXIT CHECK SKIPPED {symbol}: ATR unavailable")
            continue
        atr = float(frame["atr"].dropna().iloc[-1])
        price = float(frame["close"].iloc[-1])
        entry = float(position.avg_entry_price)
        if atr <= 0 or entry <= 0:
            continue
        stop_price = entry - 1.4 * atr
        target_price = entry + 2.8 * atr
        if price <= stop_price or price >= target_price:
            reason = "ATR STOP-LOSS" if price <= stop_price else "ATR TAKE-PROFIT"
            log(f"{reason} {symbol}: last={price:.4f}, entry={entry:.4f}")
            if not close_position(symbol):
                raise RuntimeError(f"Exit order failed for {symbol}; blocking new entries")


def run_auto_cycle(force=False):
    if not force and not in_run_window():
        log("Outside weekday 9:45 AM–3:00 PM ET trading window; skipping")
        return False

    log("=" * 54)
    log("OROCHI AUTO-TRADE CYCLE | PAPER ONLY")
    account = get_account()
    if getattr(account, "trading_blocked", False):
        raise RuntimeError("Alpaca reports trading_blocked=True")
    status = str(getattr(account, "status", "")).lower()
    if not status.endswith("active"):
        raise RuntimeError(f"Alpaca account is not active (status={status or 'unknown'})")

    log(f"Paper account equity: ${float(account.equity):,.2f}")
    # Exit management runs even when the daily loss breaker blocks new entries.
    manage_exits()
    allowed, daily_pnl = check_daily_loss_limit()
    if not allowed:
        log(f"DAILY LOSS CIRCUIT BREAKER: {daily_pnl * 100:.2f}%; no new entries")
        return True

    heat = portfolio_heat()
    log(f"Positions={heat['num_positions']} | gross exposure={heat['heat_pct'] * 100:.1f}%")
    results = run_daily_scan(execute=True)
    signals = [item for item in results if item.get("signal") != "none"]
    log(f"Scan complete: {len(results)} symbols, {len(signals)} qualified signals")
    for item in signals:
        log(f"{item['symbol']} {item['signal'].upper()} score={item.get('confluence', 0):.2f} qty={item.get('size', 0)}")
    log("Cycle complete")
    return True


def main():
    parser = argparse.ArgumentParser(description="Orochi paper auto-trader")
    parser.add_argument("--once", action="store_true", help="Run one cycle (respects market window)")
    parser.add_argument("--force", action="store_true", help="Run immediately, ignoring weekday/time window")
    args = parser.parse_args()

    if os.getenv("OROCHI_AUTO_TRADE", "").strip().lower() != "true":
        raise SystemExit("Auto trading is disabled. Set OROCHI_AUTO_TRADE=true to enable paper execution.")
    # Validate credentials/account before entering a long-running process.
    get_account()
    if args.once or args.force:
        run_auto_cycle(force=args.force)
        return

    log("Continuous scheduler started; checks every 60 seconds")
    while True:
        try:
            if in_run_window():
                run_auto_cycle(force=False)
        except Exception as exc:
            log(f"CYCLE ERROR: {exc}")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
