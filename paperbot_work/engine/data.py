"""Alpaca paper-trading data access. Clients are created lazily so imports work without keys."""
import os
from datetime import datetime, timedelta, timezone
import pandas as pd
from dotenv import load_dotenv
from .config import CRYPTO_SYMBOLS

load_dotenv()


def _credentials():
    key = os.getenv('ALPACA_API_KEY', '').strip()
    secret = os.getenv('ALPACA_SECRET_KEY', '').strip()
    if not key or not secret or key.startswith('your_') or secret.startswith('your_'):
        raise RuntimeError('Missing valid ALPACA_API_KEY / ALPACA_SECRET_KEY in .env (use PAPER keys).')
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
        crypto_map = {item.replace('/', ''): item for item in CRYPTO_SYMBOLS}
        query_symbol = symbol if '/' in symbol else crypto_map.get(symbol, symbol)
        is_crypto = query_symbol in CRYPTO_SYMBOLS
        if is_crypto:
            req = CryptoBarsRequest(symbol_or_symbols=[query_symbol], timeframe=_tf(timeframe), start=start, end=end, limit=limit)
            frame = crypto_client.get_crypto_bars(req).df
        else:
            req = StockBarsRequest(symbol_or_symbols=[query_symbol], timeframe=_tf(timeframe), start=start, end=end,
                                   limit=limit, feed=DataFeed.IEX)
            frame = stock_client.get_stock_bars(req).df
        if frame is None or frame.empty:
            return pd.DataFrame()
        if isinstance(frame.index, pd.MultiIndex):
            try:
                frame = frame.xs(query_symbol, level='symbol')
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
    """Fetch symbol-relevant headlines: Alpaca for equities, Google News RSS for crypto/fallback."""
    import xml.etree.ElementTree as ET
    import requests
    found = []
    stock_symbols = [sym for sym in symbols if '/' not in sym]
    if stock_symbols:
        try:
            from alpaca.data.historical.news import NewsClient
            from alpaca.data.requests import NewsRequest
            key, secret = _credentials()
            client = NewsClient(key, secret)
            req = NewsRequest(symbols=stock_symbols[:5], start=datetime.now(timezone.utc)-timedelta(hours=hours), limit=30)
            response = client.get_news(req)
            payload = getattr(response, 'data', response)
            items = payload.get('news', []) if isinstance(payload, dict) else payload
            for n in items:
                found.append({'headline': n.headline or '', 'summary': getattr(n, 'summary', '') or '',
                    'created_at': n.created_at, 'symbols': n.symbols or [], 'url': n.url, 'source': 'Alpaca News'})
        except Exception as exc:
            print(f'[data] Alpaca news unavailable: {exc}')
    queries = []
    for sym in symbols:
        if '/' in sym:
            queries.append((sym, f'{sym.split("/")[0]} cryptocurrency market'))
        elif not any(sym in item.get('symbols', []) for item in found):
            queries.append((sym, f'{sym} stock market'))
    cutoff = datetime.now(timezone.utc)-timedelta(hours=hours)
    for sym, query in queries[:5]:
        try:
            response = requests.get('https://news.google.com/rss/search',
                params={'q': query, 'hl': 'en-US', 'gl': 'US', 'ceid': 'US:en'},
                timeout=8, headers={'User-Agent': 'AuroraPaperResearch/1.0'})
            response.raise_for_status()
            root = ET.fromstring(response.content)
            for item in root.findall('./channel/item')[:8]:
                published = None
                pub = item.findtext('pubDate')
                if pub:
                    try:
                        from email.utils import parsedate_to_datetime
                        published = parsedate_to_datetime(pub).astimezone(timezone.utc)
                    except Exception:
                        pass
                if published and published < cutoff:
                    continue
                found.append({'headline': item.findtext('title') or '',
                    'summary': item.findtext('description') or '', 'created_at': published,
                    'symbols': [sym], 'url': item.findtext('link') or '', 'source': 'Google News RSS'})
        except Exception as exc:
            print(f'[data] RSS news unavailable for {sym}: {exc}')
    unique, seen = [], set()
    for item in found:
        key = item.get('url') or item.get('headline')
        if key and key not in seen:
            seen.add(key)
            unique.append(item)
    unique.sort(key=lambda x: x.get('created_at') or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return unique[:30]


def get_recent_orders(limit=40):
    """Return recent paper orders with broker status and fill details."""
    from alpaca.trading.requests import GetOrdersRequest
    from alpaca.trading.enums import QueryOrderStatus
    client = _clients()[0]
    request = GetOrdersRequest(status=QueryOrderStatus.ALL, limit=limit, nested=True)
    orders = client.get_orders(filter=request)
    rows = []
    for order in orders:
        side = getattr(order, 'side', '')
        status = getattr(order, 'status', '')
        rows.append({
            'id': str(getattr(order, 'id', '')),
            'symbol': str(getattr(order, 'symbol', '')),
            'side': str(getattr(side, 'value', side)).upper(),
            'qty': float(getattr(order, 'qty', 0) or 0),
            'filled_qty': float(getattr(order, 'filled_qty', 0) or 0),
            'filled_avg_price': float(getattr(order, 'filled_avg_price', 0) or 0),
            'status': str(getattr(status, 'value', status)).upper(),
            'submitted_at': getattr(order, 'submitted_at', None),
            'filled_at': getattr(order, 'filled_at', None),
        })
    rows.sort(key=lambda x: x.get('submitted_at') or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return rows


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



def submit_bracket_order(symbol, qty, take_profit_price, stop_loss_price):
    """Submit an equity entry with broker-held OTOCO exits. Paper endpoint only."""
    from alpaca.trading.requests import MarketOrderRequest, TakeProfitRequest, StopLossRequest
    from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass
    if '/' in symbol:
        raise ValueError('Alpaca crypto does not support bracket order classes; crypto entry blocked.')
    qty = float(qty)
    take_profit_price = float(take_profit_price)
    stop_loss_price = float(stop_loss_price)
    if qty <= 0 or stop_loss_price <= 0 or take_profit_price <= 0:
        raise ValueError('Invalid bracket quantity or exit price.')
    if not stop_loss_price < take_profit_price:
        raise ValueError('Stop-loss must be below take-profit for a long entry.')
    client = _clients()[0]
    request = MarketOrderRequest(
        symbol=symbol,
        qty=qty,
        side=OrderSide.BUY,
        time_in_force=TimeInForce.DAY,
        order_class=OrderClass.BRACKET,
        take_profit=TakeProfitRequest(limit_price=round(take_profit_price, 2)),
        stop_loss=StopLossRequest(stop_price=round(stop_loss_price, 2)),
    )
    return client.submit_order(order_data=request)


def close_position(symbol):
    try:
        _clients()[0].close_position(symbol)
        return True
    except Exception as exc:
        print(f'[data] Close error {symbol}: {exc}')
        return False
