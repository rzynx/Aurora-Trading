"""Alpaca paper-trading data access. Clients are created lazily so imports work without keys."""
import os
from datetime import datetime, timedelta, timezone
import pandas as pd
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # Streamlit Cloud supplies credentials through st.secrets; dotenv is optional.
    pass


def _credentials():
    """Read paper credentials from Streamlit Secrets first, then local environment."""
    key = secret = ''
    try:
        import streamlit as st
        key = str(st.secrets.get('ALPACA_API_KEY', '')).strip()
        secret = str(st.secrets.get('ALPACA_SECRET_KEY', '')).strip()
    except Exception:
        # Streamlit may be unavailable or secrets.toml may not exist in local scripts.
        pass

    key = key or os.getenv('ALPACA_API_KEY', '').strip()
    secret = secret or os.getenv('ALPACA_SECRET_KEY', '').strip()
    if not key or not secret or key.startswith('your_') or secret.startswith('your_'):
        raise RuntimeError(
            'Missing Alpaca PAPER credentials. Add ALPACA_API_KEY and '
            'ALPACA_SECRET_KEY to Streamlit Secrets or your local .env file.'
        )
    return key, secret


def _clients():
    from alpaca.trading.client import TradingClient
    from alpaca.data.historical import StockHistoricalDataClient, CryptoHistoricalDataClient
    key, secret = _credentials()
    return (TradingClient(key, secret, paper=True),
            StockHistoricalDataClient(key, secret), CryptoHistoricalDataClient(key, secret))


def get_account():
    return _clients()[0].get_account()


def get_positions():
    return {p.symbol: p for p in _clients()[0].get_all_positions()}


def _tf(timeframe):
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    mapping = {'1Min': (1, TimeFrameUnit.Minute), '5Min': (5, TimeFrameUnit.Minute),
               '15Min': (15, TimeFrameUnit.Minute), '1Hour': (1, TimeFrameUnit.Hour),
               '1Day': (1, TimeFrameUnit.Day)}
    n, unit = mapping.get(timeframe, mapping['15Min'])
    return TimeFrame(n, unit)


def get_bars(symbol, timeframe='15Min', limit=200):
    """Fetch normalized OHLCV bars; return empty data on a per-symbol API failure."""
    try:
        from alpaca.data.requests import StockBarsRequest, CryptoBarsRequest
        from alpaca.data.enums import DataFeed
        _, stock_client, crypto_client = _clients()
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=30 if timeframe in ('1Hour', '1Day') else 14)
        if '/' in symbol:
            req = CryptoBarsRequest(symbol_or_symbols=[symbol], timeframe=_tf(timeframe), start=start, end=end, limit=limit)
            frame = crypto_client.get_crypto_bars(req).df
        else:
            req = StockBarsRequest(symbol_or_symbols=[symbol], timeframe=_tf(timeframe), start=start, end=end,
                                   limit=limit, feed=DataFeed.IEX)
            frame = stock_client.get_stock_bars(req).df
        if frame is None or frame.empty:
            return pd.DataFrame()
        if isinstance(frame.index, pd.MultiIndex):
            try:
                frame = frame.xs(symbol, level='symbol')
            except (KeyError, ValueError):
                return pd.DataFrame()
        frame = frame.reset_index()
        frame.columns = [str(c).lower() for c in frame.columns]
        if 'timestamp' not in frame.columns and 'time' not in frame.columns:
            return pd.DataFrame()
        if 'timestamp' in frame.columns:
            frame.rename(columns={'timestamp': 'time'}, inplace=True)
        frame['time'] = pd.to_datetime(frame['time'], utc=True)
        required = ['open', 'high', 'low', 'close', 'volume', 'time']
        if any(c not in frame.columns for c in required):
            return pd.DataFrame()
        for col in required[:-1]:
            frame[col] = pd.to_numeric(frame[col], errors='coerce')
        return frame.dropna(subset=required).sort_values('time').tail(limit).reset_index(drop=True)
    except Exception as exc:
        print(f'[data] Error fetching {symbol} {timeframe}: {exc}')
        return pd.DataFrame()


def get_news(symbols, hours=18):
    try:
        from alpaca.data.historical.news import NewsClient
        from alpaca.data.requests import NewsRequest
        key, secret = _credentials()
        client = NewsClient(key, secret)
        stock_symbols = [s for s in symbols if '/' not in s]
        if not stock_symbols:
            return []
        req = NewsRequest(symbols=stock_symbols[:5], start=datetime.now(timezone.utc)-timedelta(hours=hours), limit=30)
        response = client.get_news(req)
        payload = getattr(response, 'data', response)
        items = payload.get('news', []) if isinstance(payload, dict) else payload
        return [{'headline': n.headline or '', 'summary': getattr(n, 'summary', '') or '',
                 'created_at': n.created_at, 'symbols': n.symbols or [], 'url': n.url} for n in items]
    except Exception as exc:
        print(f'[data] News error: {exc}')
        return []


def submit_market_order(symbol, qty, side):
    """Submit market order through paper-only TradingClient."""
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce
    client = _clients()[0]
    qty = float(qty)
    if qty <= 0:
        raise ValueError('Order quantity must be positive')
    is_crypto = '/' in symbol
    qty = round(qty, 6) if is_crypto else int(qty)
    if qty <= 0:
        raise ValueError('Quantity rounds to zero; increase account size or reduce price/stop distance')
    order = MarketOrderRequest(symbol=symbol, qty=qty,
        side=OrderSide.BUY if side.lower() == 'buy' else OrderSide.SELL,
        time_in_force=TimeInForce.GTC if is_crypto else TimeInForce.DAY)
    return client.submit_order(order)


def close_position(symbol):
    try:
        _clients()[0].close_position(symbol)
        return True
    except Exception as exc:
        print(f'[data] Close error {symbol}: {exc}')
        return False
