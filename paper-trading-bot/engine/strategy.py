"""
Main Orochi + ICT + Quant strategy engine
Runs a full multi-timeframe scan once per day (or on demand)
"""

from datetime import datetime
from typing import Optional
import pandas as pd

from .config import (
    ALL_SYMBOLS, CORE_SYMBOLS, STOCK_WATCHLIST, CRYPTO_SYMBOLS,
    HTF, MTF, LTF, MIN_CONFLUENCE_SCORE, RISK_PER_TRADE
)
from .data import get_bars, get_news, get_account, get_positions, submit_market_order, close_position
from .indicators import add_indicators, detect_regime, detect_fvgs, confluence_score
from .quant import volatility_adjusted_size, check_daily_loss_limit, portfolio_heat


def analyze_symbol(symbol: str) -> dict:
    """Full multi-TF analysis for one symbol."""
    result = {
        "symbol": symbol,
        "timestamp": datetime.utcnow().isoformat(),
        "htf": {},
        "mtf": {},
        "ltf": {},
        "fvgs": [],
        "confluence": 0.0,
        "signal": "none",
        "size": 0.0,
        "reason": "",
    }

    # Higher timeframe (bias)
    htf_df = get_bars(symbol, HTF, limit=120)
    if htf_df.empty:
        result["reason"] = "no HTF data"
        return result
    htf_df = add_indicators(htf_df)
    htf_regime = detect_regime(htf_df)
    result["htf"] = htf_regime

    # Intermediate
    mtf_df = get_bars(symbol, MTF, limit=150)
    if not mtf_df.empty:
        mtf_df = add_indicators(mtf_df)
        result["mtf"] = detect_regime(mtf_df)
        result["fvgs"] = detect_fvgs(mtf_df)

    # Entry timeframe
    ltf_df = get_bars(symbol, LTF, limit=100)
    if not ltf_df.empty:
        ltf_df = add_indicators(ltf_df)
        result["ltf"] = detect_regime(ltf_df)

    # News sentiment (optional – works without textblob)
    sentiment = 0.0
    try:
        news = get_news([symbol], hours=12)
        if news:
            try:
                from textblob import TextBlob
                texts = [n["headline"] + " " + n.get("summary", "") for n in news[:8]]
                scores = [TextBlob(t).sentiment.polarity for t in texts if t.strip()]
                sentiment = float(sum(scores) / len(scores)) if scores else 0.0
            except ImportError:
                # simple keyword fallback if textblob missing
                pos = sum(1 for n in news if any(w in (n["headline"] or "").lower() for w in ["surge", "rally", "beat", "high", "gain", "up"]))
                neg = sum(1 for n in news if any(w in (n["headline"] or "").lower() for w in ["fall", "drop", "miss", "low", "loss", "down", "cut"]))
                total = pos + neg
                sentiment = (pos - neg) / total if total else 0.0
    except Exception:
        pass

    result["sentiment"] = round(sentiment, 3)

    # Confluence
    score = confluence_score(
        regime=htf_regime,
        fvgs=result["fvgs"],
        htf_bias=htf_regime.get("bias", "neutral"),
        sentiment=sentiment,
    )
    result["confluence"] = score

    # Generate signal (aggressive)
    if score >= MIN_CONFLUENCE_SCORE:
        bias = htf_regime.get("bias")
        active_fvgs = [f for f in result["fvgs"] if not f.get("mitigated")]

        if bias == "bullish" and any(f["type"] == "bullish" for f in active_fvgs):
            result["signal"] = "long"
            result["reason"] = f"HTF bullish + active bullish FVG | score={score}"
        elif bias == "bearish" and any(f["type"] == "bearish" for f in active_fvgs):
            result["signal"] = "short"
            result["reason"] = f"HTF bearish + active bearish FVG | score={score}"
        elif bias == "bullish" and score >= 0.75:
            result["signal"] = "long"
            result["reason"] = f"Strong bullish confluence (no FVG required) | score={score}"
        elif bias == "bearish" and score >= 0.75:
            result["signal"] = "short"
            result["reason"] = f"Strong bearish confluence (no FVG required) | score={score}"
        else:
            result["reason"] = f"Score {score} but no clear FVG alignment"
    else:
        result["reason"] = f"Confluence too low ({score} < {MIN_CONFLUENCE_SCORE})"

    # Position sizing
    if result["signal"] in ("long", "short"):
        account = get_account()
        equity = float(account.equity)
        price = float(htf_df["close"].iloc[-1])
        atr = htf_regime.get("atr") or (price * 0.01)
        raw_size = volatility_adjusted_size(equity, price, atr, RISK_PER_TRADE)
        result["size"] = round(raw_size, 6)
        result["entry_price"] = price
        result["atr"] = atr

    return result


def run_daily_scan(symbols: Optional[list] = None, execute: bool = False) -> list[dict]:
    """
    Main entry point.
    Scans all symbols, returns analysis list.
    If execute=True and risk checks pass, places paper orders.
    """
    symbols = symbols or ALL_SYMBOLS
    results = []

    allowed, daily_pnl = check_daily_loss_limit()
    heat = portfolio_heat()

    print(f"\n{'='*60}")
    print(f"OROCHI + ICT SCAN  |  {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC")
    print(f"Equity: ${heat['equity']:,.2f}  |  Daily PnL: {daily_pnl*100:.2f}%  |  Heat: {heat['heat_pct']*100:.1f}%")
    print(f"{'='*60}\n")

    if not allowed:
        print("⛔ Daily loss limit reached. No new trades.")
        return results

    current_positions = get_positions()

    for symbol in symbols:
        print(f"Analyzing {symbol}...", end=" ")
        analysis = analyze_symbol(symbol)
        results.append(analysis)

        sig = analysis["signal"]
        score = analysis["confluence"]
        print(f"→ {sig.upper():5}  score={score:.2f}  |  {analysis['reason'][:60]}")

        if not execute or sig == "none":
            continue

        # Execution logic
        has_pos = symbol in current_positions or symbol.replace("/USD", "") in current_positions

        if sig == "long" and not has_pos and analysis["size"] > 0:
            try:
                order = submit_market_order(symbol, analysis["size"], "buy")
                print(f"   ✅ LONG {analysis['size']} {symbol}")
            except Exception as e:
                print(f"   ❌ Order failed: {e}")

        elif sig == "short" and has_pos:
            # For stocks we just close (Alpaca crypto has limited shorting)
            closed = close_position(symbol)
            if closed:
                print(f"   ✅ CLOSED {symbol}")

    return results


def get_dashboard_data() -> dict:
    """Aggregate everything the UI needs in one call."""
    account = get_account()
    heat = portfolio_heat()
    allowed, daily_pnl = check_daily_loss_limit()

    # Quick scan (no execution)
    scan = run_daily_scan(execute=False)

    # Sort by confluence
    scan_sorted = sorted(scan, key=lambda x: x["confluence"], reverse=True)

    return {
        "account": {
            "equity": float(account.equity),
            "cash": float(account.cash),
            "buying_power": float(account.buying_power),
            "last_equity": float(account.last_equity),
            "daily_pnl_pct": daily_pnl,
            "allowed_to_trade": allowed,
        },
        "portfolio": heat,
        "scan": scan_sorted,
        "timestamp": datetime.utcnow().isoformat(),
    }