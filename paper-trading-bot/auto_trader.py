#!/usr/bin/env python3
"""
Orochi Auto-Trader
Runs the full scan + paper execution once per trading day.

Usage:
    python auto_trader.py              # run once now, then schedule daily
    python auto_trader.py --once       # run once and exit
    python auto_trader.py --force      # ignore time checks, run immediately
"""

import os
import sys
import time
import argparse
from datetime import datetime, timedelta
import pytz

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from engine.strategy import run_daily_scan
from engine.data import get_account
from engine.quant import check_daily_loss_limit, portfolio_heat

# ====================== SETTINGS ======================
ET = pytz.timezone("America/New_York")

# Run window (Eastern Time)
RUN_AFTER_HOUR = 9          # 9:30 would be more precise, we use 9:45
RUN_AFTER_MINUTE = 45
RUN_BEFORE_HOUR = 15        # don't start new scans after 3 PM ET

# How often to wake up and check the clock (seconds)
CHECK_INTERVAL = 60 * 5     # every 5 minutes

# Log file
LOG_PATH = os.path.join(os.path.dirname(__file__), "auto_trader.log")


def log(msg: str):
    ts = datetime.now(ET).strftime("%Y-%m-%d %H:%M:%S %Z")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_PATH, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def is_weekday() -> bool:
    return datetime.now(ET).weekday() < 5  # Mon-Fri


def in_run_window() -> bool:
    now = datetime.now(ET)
    start = now.replace(hour=RUN_AFTER_HOUR, minute=RUN_AFTER_MINUTE, second=0, microsecond=0)
    end = now.replace(hour=RUN_BEFORE_HOUR, minute=0, second=0, microsecond=0)
    return start <= now <= end


def already_ran_today() -> bool:
    """Simple file-based lock so we only execute once per calendar day."""
    lock_file = os.path.join(os.path.dirname(__file__), ".last_auto_run")
    today = datetime.now(ET).strftime("%Y-%m-%d")
    if os.path.exists(lock_file):
        with open(lock_file) as f:
            last = f.read().strip()
        if last == today:
            return True
    return False


def mark_ran_today():
    lock_file = os.path.join(os.path.dirname(__file__), ".last_auto_run")
    today = datetime.now(ET).strftime("%Y-%m-%d")
    with open(lock_file, "w") as f:
        f.write(today)


def run_auto_cycle(force: bool = False) -> bool:
    """
    Execute one full scan + paper trades.
    Returns True if it actually ran.
    """
    if not force:
        if not is_weekday():
            log("Weekend — skipping")
            return False
        if not in_run_window():
            log("Outside run window (9:45–15:00 ET) — skipping")
            return False
        if already_ran_today():
            log("Already ran today — skipping")
            return False

    log("=" * 50)
    log("AUTO-TRADE CYCLE STARTING")

    try:
        account = get_account()
        equity = float(account.equity)
        log(f"Equity: ${equity:,.2f}")
    except Exception as e:
        log(f"ERROR: Cannot reach Alpaca — {e}")
        return False

    allowed, daily_pnl = check_daily_loss_limit()
    if not allowed:
        log(f"Daily loss limit hit ({daily_pnl*100:.2f}%). No new trades.")
        mark_ran_today()
        return True

    heat = portfolio_heat()
    log(f"Open positions: {heat['num_positions']} | Heat: {heat['heat_pct']*100:.1f}%")

    log("Running Orochi + ICT + Quant scan with execution...")
    results = run_daily_scan(execute=True)

    signals = [r for r in results if r["signal"] != "none"]
    log(f"Scan complete — {len(results)} symbols | {len(signals)} signals")
    for s in signals:
        log(f"  → {s['symbol']:10} {s['signal'].upper():5}  score={s['confluence']:.2f}  size={s.get('size', 0)}")

    mark_ran_today()
    log("AUTO-TRADE CYCLE DONE")
    log("=" * 50)
    return True


def main():
    parser = argparse.ArgumentParser(description="Orochi Auto-Trader")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--force", action="store_true", help="Ignore schedule, run now")
    args = parser.parse_args()

    log("Orochi Auto-Trader started")
    log(f"Mode: {'once' if args.once else 'daily scheduler'} | Force={args.force}")

    if args.once or args.force:
        run_auto_cycle(force=args.force or args.once)
        return

    # Continuous scheduler
    log(f"Scheduler active. Will trade once per day between {RUN_AFTER_HOUR}:{RUN_AFTER_MINUTE:02d}–{RUN_BEFORE_HOUR}:00 ET")
    log(f"Check interval: {CHECK_INTERVAL}s")

    while True:
        try:
            run_auto_cycle(force=False)
        except Exception as e:
            log(f"Unhandled error: {e}")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
