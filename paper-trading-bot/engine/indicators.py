"""
Technical indicators + Orochi regime + ICT FVG detection
"""

import numpy as np
import pandas as pd
from .config import (
    ATR_PERIOD, VWAP_LOOKBACK, REGIME_VOL_THRESHOLD,
    FVG_MIN_SIZE_ATR, FVG_LOOKBACK_BARS
)


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add core indicators used by the system."""
    if df.empty or len(df) < 30:
        return df

    df = df.copy()
    df["hl"] = df["high"] - df["low"]
    df["tr"] = np.maximum(
        df["hl"],
        np.maximum(
            abs(df["high"] - df["close"].shift(1)),
            abs(df["low"] - df["close"].shift(1))
        )
    )
    df["atr"] = df["tr"].rolling(ATR_PERIOD).mean()

    # Simple VWAP approximation (rolling)
    df["tp"] = (df["high"] + df["low"] + df["close"]) / 3
    df["vwap"] = (
        (df["tp"] * df["volume"]).rolling(VWAP_LOOKBACK).sum() /
        df["volume"].rolling(VWAP_LOOKBACK).sum()
    )

    # EMA for structure
    df["ema_20"] = df["close"].ewm(span=20).mean()
    df["ema_50"] = df["close"].ewm(span=50).mean()

    # Volatility regime helper
    df["atr_pct"] = df["atr"] / df["close"]
    df["vol_z"] = (
        (df["atr_pct"] - df["atr_pct"].rolling(50).mean()) /
        df["atr_pct"].rolling(50).std()
    )

    return df


def detect_regime(df: pd.DataFrame) -> dict:
    """
    Orochi-inspired regime detection (simplified Auction Market Theory).
    Returns balanced / imbalanced + direction bias.
    """
    if df.empty or len(df) < 50:
        return {"regime": "unknown", "bias": "neutral", "strength": 0.0}

    latest = df.iloc[-1]
    atr = latest.get("atr", 0)
    close = latest["close"]
    vwap = latest.get("vwap", close)

    # Distance from VWAP in ATR units
    dist_atr = abs(close - vwap) / atr if atr > 0 else 0

    # Recent range vs ATR
    recent = df.tail(20)
    range_size = recent["high"].max() - recent["low"].min()
    range_atr = range_size / atr if atr > 0 else 1

    # Structure
    ema20 = latest.get("ema_20", close)
    ema50 = latest.get("ema_50", close)

    if dist_atr < 0.6 and range_atr < REGIME_VOL_THRESHOLD:
        regime = "balanced"
        strength = 0.4
    else:
        regime = "imbalanced"
        strength = min(1.0, dist_atr / 2)

    # Bias
    if close > vwap and ema20 > ema50:
        bias = "bullish"
    elif close < vwap and ema20 < ema50:
        bias = "bearish"
    else:
        bias = "neutral"

    return {
        "regime": regime,
        "bias": bias,
        "strength": round(strength, 2),
        "dist_vwap_atr": round(dist_atr, 2),
        "vwap": round(vwap, 4),
        "atr": round(atr, 4),
    }


def detect_fvgs(df: pd.DataFrame) -> list[dict]:
    """
    ICT Fair Value Gap detection (3-candle imbalance).
    Bullish FVG: candle1 high < candle3 low
    Bearish FVG: candle1 low > candle3 high
    """
    if df.empty or len(df) < 10:
        return []

    fvgs = []
    lookback = min(FVG_LOOKBACK_BARS, len(df) - 3)
    atr = df["atr"].iloc[-1] if "atr" in df.columns else df["close"].std()

    for i in range(len(df) - lookback, len(df) - 2):
        c1 = df.iloc[i]
        c2 = df.iloc[i + 1]
        c3 = df.iloc[i + 2]

        # Bullish FVG
        if c1["high"] < c3["low"]:
            gap_size = c3["low"] - c1["high"]
            if gap_size >= atr * FVG_MIN_SIZE_ATR:
                fvgs.append({
                    "type": "bullish",
                    "top": round(c3["low"], 4),
                    "bottom": round(c1["high"], 4),
                    "mid": round((c3["low"] + c1["high"]) / 2, 4),
                    "size": round(gap_size, 4),
                    "bar_index": i + 1,
                    "time": c2.get("time", None),
                    "mitigated": False,
                })

        # Bearish FVG
        if c1["low"] > c3["high"]:
            gap_size = c1["low"] - c3["high"]
            if gap_size >= atr * FVG_MIN_SIZE_ATR:
                fvgs.append({
                    "type": "bearish",
                    "top": round(c1["low"], 4),
                    "bottom": round(c3["high"], 4),
                    "mid": round((c1["low"] + c3["high"]) / 2, 4),
                    "size": round(gap_size, 4),
                    "bar_index": i + 1,
                    "time": c2.get("time", None),
                    "mitigated": False,
                })

    # Mark mitigation (price has traded through the gap)
    current_price = df["close"].iloc[-1]
    for fvg in fvgs:
        if fvg["type"] == "bullish" and current_price < fvg["bottom"]:
            fvg["mitigated"] = True
        elif fvg["type"] == "bearish" and current_price > fvg["top"]:
            fvg["mitigated"] = True

    # Return only unmitigated, most recent first
    active = [f for f in fvgs if not f["mitigated"]]
    return active[-6:]  # keep last few


def confluence_score(
    regime: dict,
    fvgs: list[dict],
    htf_bias: str,
    sentiment: float = 0.0,
) -> float:
    """
    Basic quantitative confluence scoring (0-1).
    Aggressive threshold lives in config.
    """
    score = 0.0

    # Regime weight
    if regime["regime"] == "imbalanced":
        score += 0.25 * regime["strength"]
    else:
        score += 0.10

    # Bias alignment
    if regime["bias"] == htf_bias and htf_bias != "neutral":
        score += 0.25
    elif regime["bias"] == "neutral":
        score += 0.08

    # Active FVG in direction of bias
    relevant_fvgs = [
        f for f in fvgs
        if (f["type"] == "bullish" and htf_bias == "bullish") or
           (f["type"] == "bearish" and htf_bias == "bearish")
    ]
    if relevant_fvgs:
        score += 0.30
        # Bonus for larger gaps
        best = max(relevant_fvgs, key=lambda x: x["size"])
        score += min(0.10, best["size"] / (regime.get("atr", 1) * 3))

    # Sentiment (news)
    if sentiment > 0.15 and htf_bias == "bullish":
        score += 0.12
    elif sentiment < -0.15 and htf_bias == "bearish":
        score += 0.12
    elif abs(sentiment) < 0.1:
        score += 0.04

    return round(min(1.0, score), 3)