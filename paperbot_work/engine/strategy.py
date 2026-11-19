"""Orochi + ICT scan and guarded Alpaca paper execution."""
from datetime import datetime, timezone
from typing import Optional
import math
from .config import ALL_SYMBOLS, HTF, MTF, LTF, MIN_CONFLUENCE_SCORE, RISK_PER_TRADE, MAX_OPEN_POSITIONS
from .data import get_bars, get_news, get_account, get_positions, submit_market_order, close_position
from .indicators import add_indicators, detect_regime, detect_fvgs, confluence_score
from .quant import volatility_adjusted_size, check_daily_loss_limit, portfolio_heat


def _news_sentiment(symbol):
    news = get_news([symbol], hours=12)
    if not news:
        return 0.0
    try:
        from textblob import TextBlob
        scores = [TextBlob((n.get('headline') or '')+' '+(n.get('summary') or '')).sentiment.polarity for n in news[:8]]
        return float(sum(scores)/len(scores)) if scores else 0.0
    except ImportError:
        # Conservative fallback: whole-phrase matching avoids counting "inflation rises" as positive.
        positive = ('shares rise', 'stock rises', 'profit beats', 'revenue beats', 'raises guidance', 'record high', 'surges', 'rallies')
        negative = ('shares fall', 'stock falls', 'profit misses', 'revenue misses', 'cuts guidance', 'record low', 'plunges', 'sells off')
        score = 0
        for item in news[:8]:
            text = ((item.get('headline') or '')+' '+(item.get('summary') or '')).lower()
            score += int(any(p in text for p in positive)) - int(any(n in text for n in negative))
        return max(-1.0, min(1.0, score/max(1, min(len(news), 8))))


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

    sentiment = _news_sentiment(symbol)
    result['sentiment'] = round(sentiment, 3)
    score = confluence_score(htf_regime, result['fvgs'], htf_regime.get('bias', 'neutral'), sentiment)
    result['confluence'] = score
    bias = htf_regime.get('bias')
    active = [f for f in result['fvgs'] if not f.get('mitigated')]
    aligned = any(f.get('type') == ('bullish' if bias == 'bullish' else 'bearish') for f in active) if bias in ('bullish', 'bearish') else False
    if score >= MIN_CONFLUENCE_SCORE and bias in ('bullish', 'bearish') and aligned:
        result['signal'] = 'long' if bias == 'bullish' else 'short'
        result['reason'] = f'{bias.title()} HTF bias + aligned active FVG | score={score:.3f}'
    else:
        result['reason'] = f'No qualified setup (score={score:.3f}, bias={bias}, aligned FVG={aligned})'

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
        print('BLOCKED: daily loss limit reached or risk check unavailable; no orders sent.')
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
        try:
            order = submit_market_order(symbol, analysis['size'], 'buy')
            order_id = str(getattr(order, 'id', 'submitted'))
            analysis['execution_status'] = 'PAPER BUY SUBMITTED'
            analysis['order_id'] = order_id
            print(f"   PAPER BUY submitted: {analysis['size']} {symbol} | order={order_id}")
            # Reserve slot/exposure for this scan to avoid stacking correlated orders.
            positions[symbol] = True
            new_entries += 1
            heat['heat_pct'] += min(analysis['size']*analysis.get('entry_price', 0)/max(heat['equity'], 1), 0.25)
        except Exception as exc:
            analysis['execution_status'] = f'ORDER FAILED: {exc}'
            print(f'   ORDER FAILED {symbol}: {exc}')
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
