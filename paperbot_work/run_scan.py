#!/usr/bin/env python3
"""
CLI runner — execute the daily Orochi + ICT scan
Usage:
    python run_scan.py              # analysis only
    python run_scan.py --execute    # analysis + paper orders
"""

import argparse
from engine.strategy import run_daily_scan

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Orochi + ICT Paper Trading Scan")
    parser.add_argument("--execute", action="store_true", help="Place paper orders")
    args = parser.parse_args()

    results = run_daily_scan(execute=args.execute)

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    signals = [r for r in results if r["signal"] != "none"]
    print(f"Total symbols scanned : {len(results)}")
    print(f"Signals generated     : {len(signals)}")
    for s in signals:
        print(f"  → {s['symbol']:10} {s['signal'].upper():5}  score={s['confluence']:.2f}  size={s.get('size', 0)}")
    print()