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
    qty = int(float(qty))
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
        time_in_force=TimeInForce.GTC,
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


def get_options_liquidity_surface(underlying, spot_price, days_ahead=45):
    """
    Fetch Alpaca option contracts + indicative snapshots for research visuals.
    Returns contract-level quote, Greeks, IV, OI and displayed top-of-book size.
    The free indicative feed is delayed/derived, not OPRA depth or institutional order flow.
    """
    import requests
    from datetime import date, timedelta

    key, secret = _credentials()
    headers = {
        "APCA-API-KEY-ID": key,
        "APCA-API-SECRET-KEY": secret,
        "accept": "application/json",
    }
    today = date.today()
    params = {
        "underlying_symbols": underlying,
        "status": "active",
        "expiration_date_gte": today.isoformat(),
        "expiration_date_lte": (today + timedelta(days=int(days_ahead))).isoformat(),
        "strike_price_gte": round(float(spot_price) * 0.80, 2),
        "strike_price_lte": round(float(spot_price) * 1.20, 2),
        "limit": 10000,
    }
    response = requests.get(
        "https://paper-api.alpaca.markets/v2/options/contracts",
        headers=headers, params=params, timeout=20,
    )
    response.raise_for_status()
    contracts = response.json().get("option_contracts", [])
    if not contracts:
        return pd.DataFrame()

    snapshots = {}
    page_token = None
    for _ in range(5):
        snapshot_params = {"feed": "indicative", "limit": 1000}
        if page_token:
            snapshot_params["page_token"] = page_token
        snap_response = requests.get(
            f"https://data.alpaca.markets/v1beta1/options/snapshots/{underlying}",
            headers=headers, params=snapshot_params, timeout=20,
        )
        snap_response.raise_for_status()
        payload = snap_response.json()
        snapshots.update(payload.get("snapshots", {}))
        page_token = payload.get("next_page_token")
        if not page_token:
            break

    rows = []
    for contract in contracts:
        symbol = contract.get("symbol")
        snap = snapshots.get(symbol, {})
        quote = snap.get("latestQuote") or {}
        trade = snap.get("latestTrade") or {}
        greeks = snap.get("greeks") or {}
        bid = float(quote.get("bp") or 0)
        ask = float(quote.get("ap") or 0)
        bid_size = float(quote.get("bs") or 0)
        ask_size = float(quote.get("as") or 0)
        mid = (bid + ask) / 2 if bid > 0 and ask > 0 else 0
        spread_pct = ((ask - bid) / mid * 100) if mid > 0 and ask >= bid else None
        dte = (date.fromisoformat(contract["expiration_date"]) - today).days
        rows.append({
            "contract": symbol,
            "underlying": underlying,
            "type": contract.get("type", "").upper(),
            "expiration": contract.get("expiration_date"),
            "dte": dte,
            "strike": float(contract.get("strike_price") or 0),
            "open_interest": float(contract.get("open_interest") or 0),
            "open_interest_date": contract.get("open_interest_date"),
            "bid": bid or None,
            "ask": ask or None,
            "mid": mid or None,
            "bid_size": bid_size,
            "ask_size": ask_size,
            "bid_depth_usd": bid * bid_size * 100,
            "ask_depth_usd": ask * ask_size * 100,
            "spread_pct": spread_pct,
            "trade_size": float(trade.get("s") or 0),
            "iv": float(snap.get("impliedVolatility") or 0) * 100,
            "delta": float(greeks.get("delta") or 0),
            "gamma": float(greeks.get("gamma") or 0),
            "theta": float(greeks.get("theta") or 0),
            "vega": float(greeks.get("vega") or 0),
            "quote_time": quote.get("t"),
            "feed": "INDICATIVE",
        })
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame = frame[(frame["iv"] > 0) | frame["bid"].notna() | frame["ask"].notna()]
    frame["two_sided_depth_usd"] = frame[["bid_depth_usd", "ask_depth_usd"]].min(axis=1)
    frame["liquidity_proxy"] = (
        frame["open_interest"].clip(lower=0).pow(0.5)
        * frame["two_sided_depth_usd"].clip(lower=0).pow(0.5)
    )
    return frame.sort_values(["expiration", "strike", "type"]).reset_index(drop=True)

def get_latest_stock_trades(symbols):
    """Fetch one batched latest-trade snapshot for a stock watchlist from Alpaca IEX."""
    stock_symbols = [str(symbol).strip().upper() for symbol in symbols if str(symbol).strip() and "/" not in str(symbol)]
    if not stock_symbols:
        return pd.DataFrame()
    try:
        from alpaca.data.requests import StockLatestTradeRequest
        from alpaca.data.enums import DataFeed
        _, stock_client, _ = _clients()
        request = StockLatestTradeRequest(symbol_or_symbols=stock_symbols, feed=DataFeed.IEX)
        payload = stock_client.get_stock_latest_trade(request)
        rows = []
        for symbol in stock_symbols:
            trade = payload.get(symbol) if isinstance(payload, dict) else None
            if trade is None:
                continue
            price = float(getattr(trade, "price", 0) or 0)
            if price <= 0:
                continue
            timestamp = getattr(trade, "timestamp", None)
            rows.append({
                "symbol": symbol,
                "price": price,
                "size": float(getattr(trade, "size", 0) or 0),
                "trade_time": timestamp,
                "feed": "IEX",
            })
        return pd.DataFrame(rows)
    except Exception as exc:
        print(f"[data] Latest stock trades unavailable: {exc}")
        return pd.DataFrame()

