"""Orochi + ICT scan and guarded Alpaca paper execution."""
from datetime import datetime, timezone
from typing import Optional
import math
from .config import ALL_SYMBOLS, HTF, MTF, LTF, MIN_CONFLUENCE_SCORE, RISK_PER_TRADE, MAX_OPEN_POSITIONS
from .data import get_bars, get_news, get_account, get_positions, submit_bracket_order, close_position
from .indicators import add_indicators, detect_regime, detect_fvgs, confluence_score
from .quant import volatility_adjusted_size, check_daily_loss_limit, portfolio_heat


def _news_analysis(symbol):
    """Score recent relevant headlines with a small finance-specific phrase lexicon."""
    items = get_news([symbol], hours=12)
    positive = ('beats expectations', 'profit beats', 'revenue beats', 'raises guidance',
        'upgrade', 'price target raised', 'strong demand', 'record revenue', 'approval',
        'partnership', 'surges', 'rallies', 'adoption grows', 'inflows')
    negative = ('misses expectations', 'profit miss', 'revenue miss', 'cuts guidance',
        'downgrade', 'price target cut', 'investigation', 'lawsuit', 'hack', 'exploit',
        'outage', 'bankruptcy', 'sec charges', 'liquidation', 'plunges', 'selloff',
        'sells off', 'outflows')
    scores = []
    for item in items[:10]:
        text = ((item.get('headline') or '') + ' ' + (item.get('summary') or '')).lower()
        pos = sum(1 for phrase in positive if phrase in text)
        neg = sum(1 for phrase in negative if phrase in text)
        scores.append(max(-1.0, min(1.0, (pos-neg) / max(1, pos+neg))))
    sentiment = float(sum(scores)/len(scores)) if scores else 0.0
    return round(sentiment, 3), items[:6]


def _news_sentiment(symbol):
    return _news_analysis(symbol)[0]


def analyze_symbol(symbol: str) -> dict:
    result = {'symbol': symbol, 'timestamp': datetime.now(timezone.utc).isoformat(), 'htf': {}, 'mtf': {},
              'ltf': {}, 'fvgs': [], 'confluence': 0.0, 'signal': 'none', 'size': 0.0, 'reason': ''}
    htf_df = get_bars(symbol, HTF, limit=120)
    if htf_df.empty:
        result['reason'] = 'no HTF data'
        return result
    htf_df = add_indicators(htf_df)
    htf_regime = detect_regime(htf_df)
    result['htf'] = htf_regime
    if htf_regime.get('regime') == 'unknown':
        result['reason'] = 'insufficient or invalid HTF indicators'
        return result

    mtf_df = get_bars(symbol, MTF, limit=150)
    if not mtf_df.empty:
        mtf_df = add_indicators(mtf_df)
        result['mtf'] = detect_regime(mtf_df)
        result['fvgs'] = detect_fvgs(mtf_df)
    ltf_df = get_bars(symbol, LTF, limit=100)
    if not ltf_df.empty:
        result['ltf'] = detect_regime(add_indicators(ltf_df))

    sentiment, headlines = _news_analysis(symbol)
    result['sentiment'] = sentiment
    result['news_headlines'] = headlines
    result['news_count'] = len(headlines)
    score = confluence_score(htf_regime, result['fvgs'], htf_regime.get('bias', 'neutral'), sentiment)
    result['confluence'] = score
    bias = htf_regime.get('bias')
    active = [f for f in result['fvgs'] if not f.get('mitigated')]
    aligned = any(f.get('type') == ('bullish' if bias == 'bullish' else 'bearish') for f in active) if bias in ('bullish', 'bearish') else False
    news_note = f"news {sentiment:+.2f} across {len(headlines)} headlines"
    adverse_news_veto = bias == 'bullish' and sentiment <= -0.35 and len(headlines) > 0
    if score >= MIN_CONFLUENCE_SCORE and bias in ('bullish', 'bearish') and aligned and not adverse_news_veto:
        result['signal'] = 'long' if bias == 'bullish' else 'short'
        result['reason'] = f'{bias.title()} HTF bias + aligned active FVG + {news_note} | score={score:.3f}'
    elif adverse_news_veto:
        result['reason'] = f'LONG VETO: adverse news conflicts with bullish structure | {news_note}'
    else:
        result['reason'] = f'No qualified setup (score={score:.3f}, bias={bias}, aligned FVG={aligned}; {news_note})'

    if result['signal'] != 'none':
        price = float(htf_df['close'].iloc[-1])
        atr = float(htf_regime.get('atr') or 0)
        account = get_account()
        result['size'] = round(volatility_adjusted_size(float(account.equity), price, atr, RISK_PER_TRADE), 6)
        result['entry_price'] = price
        result['atr'] = atr
    return result


def run_daily_scan(symbols: Optional[list] = None, execute: bool = False, max_new_entries: Optional[int] = None) -> list[dict]:
    symbols = symbols or ALL_SYMBOLS
    results = []
    allowed, daily_pnl = check_daily_loss_limit()
    heat = portfolio_heat()
    print(f"\n{'='*60}\nOROCHI + ICT SCAN | {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC")
    print(f"Equity: ${heat['equity']:,.2f} | Daily PnL: {daily_pnl*100:.2f}% | Exposure: {heat['heat_pct']*100:.1f}%\n{'='*60}")
    if execute and not allowed:
        print('BLOCKED: daily P&L limit reached or risk check unavailable; no orders sent.')
        return results
    positions = get_positions() if execute else {}
    new_entries = 0
    for symbol in symbols:
        print(f'Analyzing {symbol}...', end=' ')
        try:
            analysis = analyze_symbol(symbol)
        except Exception as exc:
            analysis = {'symbol': symbol, 'signal': 'none', 'confluence': 0.0, 'size': 0.0,
                        'reason': f'analysis error: {exc}', 'htf': {}, 'sentiment': 0.0, 'fvgs': []}
        results.append(analysis)
        print(f"→ {analysis['signal'].upper():5} score={analysis['confluence']:.2f} | {analysis.get('reason','')[:80]}")
        if not execute:
            continue
        if analysis['signal'] == 'none':
            analysis['execution_status'] = 'NO TRADE — no qualified setup'
            continue
        # This bot only opens long positions; bearish signals close existing longs.
        pos_key = symbol if symbol in positions else symbol.replace('/USD', '')
        has_pos = pos_key in positions
        if analysis['signal'] == 'short':
            if has_pos and float(positions[pos_key].qty) > 0:
                closed = close_position(pos_key)
                analysis['execution_status'] = 'PAPER CLOSE SUBMITTED' if closed else 'PAPER CLOSE FAILED'
            else:
                analysis['execution_status'] = 'NO NEW SHORT — short entries disabled'
            continue
        if has_pos:
            analysis['execution_status'] = 'SKIPPED — position already open'
            continue
        if analysis['size'] <= 0:
            analysis['execution_status'] = 'SKIPPED — calculated size is zero'
            continue
        if max_new_entries is not None and new_entries >= max_new_entries:
            analysis['execution_status'] = 'SKIPPED — per-scan entry limit reached'
            continue
        if len(positions) >= MAX_OPEN_POSITIONS:
            analysis['execution_status'] = 'BLOCKED — maximum open positions reached'
            print(f'   BLOCKED {symbol}: max open positions reached')
            continue
        if heat['heat_pct'] >= 0.75:
            analysis['execution_status'] = 'BLOCKED — gross exposure at/above 75%'
            print(f'   BLOCKED {symbol}: portfolio gross exposure at/above 75%')
            continue
        # Crypto is deliberately blocked until a broker-supported, linked
        # protective-exit implementation is available. Alpaca currently supports
        # only simple order classes for crypto, not bracket/OCO orders.
        if '/' in symbol:
            analysis['execution_status'] = 'BLOCKED — crypto entries paused: broker-linked stop/target unavailable'
            print(f'   BLOCKED {symbol}: crypto protective exits are not safely supported')
            continue
        try:
            entry = float(analysis.get('entry_price') or 0)
            atr = float(analysis.get('atr') or 0)
            stop_price = entry - 1.4 * atr
            target_price = entry + 2.8 * atr
            if entry <= 0 or atr <= 0 or stop_price <= 0:
                raise ValueError('Invalid entry/ATR; refusing unprotected order')
            order = submit_bracket_order(symbol, analysis['size'], target_price, stop_price)
            order_id = str(getattr(order, 'id', 'submitted'))
            analysis['execution_status'] = 'PAPER BRACKET BUY SUBMITTED'
            analysis['order_id'] = order_id
            analysis['stop_loss_price'] = round(stop_price, 2)
            analysis['take_profit_price'] = round(target_price, 2)
            print(f"   PAPER BRACKET BUY submitted: {analysis['size']} {symbol} | stop={stop_price:.2f} target={target_price:.2f} | order={order_id}")
            positions[symbol] = True
            new_entries += 1
            heat['heat_pct'] += min(analysis['size']*entry/max(heat['equity'], 1), 0.25)
        except Exception as exc:
            analysis['execution_status'] = f'BRACKET ORDER FAILED: {exc}'
            print(f'   BRACKET ORDER FAILED {symbol}: {exc}')
    return results


def get_dashboard_data():
    account = get_account()
    heat = portfolio_heat()
    allowed, daily_pnl = check_daily_loss_limit()
    scan = run_daily_scan(execute=False)
    return {'account': {'equity': float(account.equity), 'cash': float(account.cash),
            'buying_power': float(account.buying_power), 'last_equity': float(account.last_equity),
            'daily_pnl_pct': daily_pnl, 'allowed_to_trade': allowed},
            'portfolio': heat, 'scan': sorted(scan, key=lambda x: x['confluence'], reverse=True),
            'timestamp': datetime.now(timezone.utc).isoformat()}
