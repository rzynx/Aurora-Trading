"""
Basic Quantitative Finance layer
- Volatility-adjusted position sizing
- Risk controls
- Simple expectancy tracking
"""

import numpy as np
import pandas as pd
from .config import (
    RISK_PER_TRADE, MAX_POSITION_PCT, DAILY_LOSS_LIMIT, VOL_LOOKBACK
)
from .data import get_account, get_positions


def volatility_adjusted_size(
    equity: float,
    price: float,
    atr: float,
    risk_pct: float = RISK_PER_TRADE,
    stop_atr_mult: float = 1.4,
) -> float:
    """
    Position size so that a stop of `stop_atr_mult * ATR` risks `risk_pct` of equity.
    """
    if atr <= 0 or price <= 0 or equity <= 0:
        return 0.0

    risk_dollars = equity * risk_pct
    stop_distance = atr * stop_atr_mult
    shares = risk_dollars / stop_distance

    # Cap by max position %
    max_shares = (equity * MAX_POSITION_PCT) / price
    shares = min(shares, max_shares)

    return max(0.0, shares)


def check_daily_loss_limit() -> tuple[bool, float]:
    """
    Returns (allowed_to_trade, current_daily_pnl_pct)
    """
    try:
        account = get_account()
        equity = float(account.equity)
        last_equity = float(account.last_equity)
        if last_equity <= 0:
            return True, 0.0
        daily_pnl_pct = (equity - last_equity) / last_equity
        allowed = daily_pnl_pct > -DAILY_LOSS_LIMIT
        return allowed, round(daily_pnl_pct, 4)
    except Exception:
        return True, 0.0


def portfolio_heat() -> dict:
    """Simple portfolio heat / exposure summary."""
    account = get_account()
    positions = get_positions()
    equity = float(account.equity)

    total_long = 0.0
    total_short = 0.0
    by_symbol = {}

    for sym, pos in positions.items():
        mv = float(pos.market_value)
        by_symbol[sym] = {
            "qty": float(pos.qty),
            "market_value": mv,
            "unrealized_pl": float(pos.unrealized_pl),
            "side": "long" if float(pos.qty) > 0 else "short",
        }
        if mv > 0:
            total_long += mv
        else:
            total_short += abs(mv)

    return {
        "equity": equity,
        "long_exposure": total_long,
        "short_exposure": total_short,
        "net_exposure": total_long - total_short,
        "gross_exposure": total_long + total_short,
        "heat_pct": (total_long + total_short) / equity if equity > 0 else 0,
        "positions": by_symbol,
        "num_positions": len(positions),
    }


def simple_expectancy(wins: list[float], losses: list[float]) -> dict:
    """Basic expectancy calculation from historical trade list."""
    if not wins and not losses:
        return {"expectancy": 0.0, "win_rate": 0.0, "profit_factor": 0.0, "avg_win": 0, "avg_loss": 0}

    n = len(wins) + len(losses)
    win_rate = len(wins) / n if n else 0
    avg_win = np.mean(wins) if wins else 0
    avg_loss = abs(np.mean(losses)) if losses else 0
    expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 1
    profit_factor = gross_profit / gross_loss if gross_loss else 0

    return {
        "expectancy": round(expectancy, 4),
        "win_rate": round(win_rate, 3),
        "profit_factor": round(profit_factor, 3),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "n_trades": n,
    }