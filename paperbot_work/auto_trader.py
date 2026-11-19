#!/usr/bin/env python3
"""Orochi scheduled Alpaca paper auto-trader.

Stocks are scanned during the weekday session. Crypto is scanned 24/7.
Hosted cron invokes one cycle per run; all broker clients use paper=True.
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
from engine.config import CORE_SYMBOLS, STOCK_WATCHLIST, CRYPTO_SYMBOLS
from engine.data import get_account, get_positions, get_bars, close_position
from engine.indicators import add_indicators
from engine.quant import check_daily_loss_limit, portfolio_heat

ET = pytz.timezone("America/New_York")
RUN_AFTER_HOUR, RUN_AFTER_MINUTE = 9, 45
RUN_BEFORE_HOUR = 15
CHECK_INTERVAL = 60
STOCK_SYMBOLS = CORE_SYMBOLS + STOCK_WATCHLIST
CRYPTO_POSITION_SYMBOLS = {symbol.replace("/", "") for symbol in CRYPTO_SYMBOLS}


def log(message):
    print(f"[{datetime.now(ET):%Y-%m-%d %H:%M:%S %Z}] {message}", flush=True)


def in_run_window():
    now = datetime.now(ET)
    start = now.replace(hour=RUN_AFTER_HOUR, minute=RUN_AFTER_MINUTE, second=0, microsecond=0)
    end = now.replace(hour=RUN_BEFORE_HOUR, minute=0, second=0, microsecond=0)
    return now.weekday() < 5 and start <= now <= end


def manage_exits(stock_session=False):
    """Monitor crypto continuously and stocks only during the stock session."""
    for symbol, position in get_positions().items():
        if float(position.qty) <= 0:
            continue
        is_crypto = symbol in CRYPTO_POSITION_SYMBOLS or "/" in symbol
        if not is_crypto and not stock_session:
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
    stock_session = force or in_run_window()
    log("=" * 54)
    log("AURORA / OROCHI AUTO-TRADE CYCLE | PAPER ONLY")
    account = get_account()
    if getattr(account, "trading_blocked", False):
        raise RuntimeError("Alpaca reports trading_blocked=True")
    status = str(getattr(account, "status", "")).lower()
    if not status.endswith("active"):
        raise RuntimeError(f"Alpaca account is not active (status={status or 'unknown'})")

    log(f"Paper account equity: ${float(account.equity):,.2f}")
    # Crypto exits run every cycle; stock exits run only during stock market hours.
    manage_exits(stock_session=stock_session)
    allowed, daily_pnl = check_daily_loss_limit()
    if not allowed:
        log(f"DAILY P&L LIMIT LOCK: {daily_pnl * 100:.2f}%; no new entries")
        return True

    heat = portfolio_heat()
    log(f"Positions={heat['num_positions']} | gross exposure={heat['heat_pct'] * 100:.1f}%")

    crypto_results = run_daily_scan(symbols=CRYPTO_SYMBOLS, execute=True)
    crypto_signals = [item for item in crypto_results if item.get("signal") != "none"]
    log(f"Crypto scan complete: {len(crypto_results)} symbols, {len(crypto_signals)} qualified signals")

    if stock_session:
        stock_results = run_daily_scan(symbols=STOCK_SYMBOLS, execute=True)
        stock_signals = [item for item in stock_results if item.get("signal") != "none"]
        log(f"Stock scan complete: {len(stock_results)} symbols, {len(stock_signals)} qualified signals")
    else:
        log("Stock scan skipped: outside weekday 9:45 AM–3:00 PM ET session")

    log("Cycle complete")
    return True


def main():
    parser = argparse.ArgumentParser(description="AURORA / Orochi paper auto-trader")
    parser.add_argument("--once", action="store_true", help="Run one cycle; crypto always, stocks during market hours")
    parser.add_argument("--force", action="store_true", help="Run immediately, including stock scan outside market hours")
    args = parser.parse_args()

    if os.getenv("OROCHI_AUTO_TRADE", "").strip().lower() != "true":
        raise SystemExit("Auto trading is disabled. Set OROCHI_AUTO_TRADE=true to enable paper execution.")
    # Validate credentials/account before entering a long-running process.
    get_account()
    if args.once or args.force:
        run_auto_cycle(force=args.force)
        return

    log("Continuous scheduler started; crypto checks every 60 seconds")
    while True:
        try:
            run_auto_cycle(force=False)
        except Exception as exc:
            log(f"CYCLE ERROR: {exc}")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
