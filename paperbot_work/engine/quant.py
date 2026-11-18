"""Position sizing and fail-safe paper-account risk controls."""
import numpy as np
from .config import RISK_PER_TRADE, MAX_POSITION_PCT, DAILY_LOSS_LIMIT
from .data import get_account, get_positions


def volatility_adjusted_size(equity, price, atr, risk_pct=RISK_PER_TRADE, stop_atr_mult=1.4):
    values = (equity, price, atr, risk_pct, stop_atr_mult)
    if any(not np.isfinite(float(v)) for v in values) or min(values) <= 0:
        return 0.0
    risk_dollars = float(equity) * float(risk_pct)
    stop_distance = float(atr) * float(stop_atr_mult)
    units = min(risk_dollars / stop_distance, (float(equity) * MAX_POSITION_PCT) / float(price))
    return max(0.0, units)


def check_daily_loss_limit():
    """Fail closed: if account/risk data cannot be checked, block new orders."""
    try:
        account = get_account()
        equity, prior = float(account.equity), float(account.last_equity)
        if prior <= 0 or not np.isfinite(equity):
            return False, 0.0
        pnl = (equity-prior)/prior
        return pnl > -DAILY_LOSS_LIMIT, round(pnl, 4)
    except Exception as exc:
        print(f'[risk] Unable to verify daily loss limit; blocking trades: {exc}')
        return False, 0.0


def portfolio_heat():
    account = get_account()
    positions = get_positions()
    equity = float(account.equity)
    long_value = short_value = 0.0
    by_symbol = {}
    for sym, pos in positions.items():
        qty, mv = float(pos.qty), float(pos.market_value)
        by_symbol[sym] = {'qty': qty, 'market_value': mv, 'unrealized_pl': float(pos.unrealized_pl),
                          'side': 'long' if qty > 0 else 'short'}
        if qty > 0:
            long_value += abs(mv)
        else:
            short_value += abs(mv)
    gross = long_value + short_value
    return {'equity': equity, 'long_exposure': long_value, 'short_exposure': short_value,
            'net_exposure': long_value-short_value, 'gross_exposure': gross,
            'heat_pct': gross/equity if equity > 0 else 0.0,
            'positions': by_symbol, 'num_positions': len(positions)}


def simple_expectancy(wins, losses):
    if not wins and not losses:
        return {'expectancy': 0.0, 'win_rate': 0.0, 'profit_factor': 0.0, 'avg_win': 0.0, 'avg_loss': 0.0, 'n_trades': 0}
    n = len(wins)+len(losses)
    win_rate = len(wins)/n
    avg_win = float(np.mean(wins)) if wins else 0.0
    avg_loss = abs(float(np.mean(losses))) if losses else 0.0
    gross_loss = abs(sum(losses))
    return {'expectancy': round(win_rate*avg_win-(1-win_rate)*avg_loss, 4),
            'win_rate': round(win_rate, 3), 'profit_factor': round(sum(wins)/gross_loss, 3) if gross_loss else float('inf'),
            'avg_win': round(avg_win, 2), 'avg_loss': round(avg_loss, 2), 'n_trades': n}
