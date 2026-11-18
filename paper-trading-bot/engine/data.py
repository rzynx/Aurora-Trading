"""
Data layer - Alpaca market data + news
"""

import os
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd
from dotenv import load_dotenv

from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient, CryptoHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, CryptoBarsRequest, NewsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.data.enums import DataFeed
from alpaca.trading.requests import GetAssetsRequest
from alpaca.trading.enums import AssetClass

load_dotenv()

API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")

if not API_KEY or not SECRET_KEY:
    raise ValueError("Missing ALPACA_API_KEY or ALPACA_SECRET_KEY in .env")

trading_client = TradingClient(API_KEY, SECRET_KEY, paper=True)
stock_data = StockHistoricalDataClient(API_KEY, SECRET_KEY)
crypto_data = CryptoHistoricalDataClient(API_KEY, SECRET_KEY)


def get_account():
    return trading_client.get_account()


def get_positions():
    return {p.symbol: p for p in trading_client.get_all_positions()}


def _tf(timeframe: str) -> TimeFrame:
    mapping = {
        "1Min": TimeFrame(1, TimeFrameUnit.Minute),
        "5Min": TimeFrame(5, TimeFrameUnit.Minute),
        "15Min": TimeFrame(15, TimeFrameUnit.Minute),
        "1Hour": TimeFrame(1, TimeFrameUnit.Hour),
        "1Day": TimeFrame(1, TimeFrameUnit.Day),
    }
    return mapping.get(timeframe, TimeFrame(15, TimeFrameUnit.Minute))


def get_bars(symbol: str, timeframe: str = "15Min", limit: int = 200) -> pd.DataFrame:
    """Fetch OHLCV bars. Handles both stocks and crypto."""
    is_crypto = "/" in symbol
    end = datetime.utcnow()
    start = end - timedelta(days=14 if timeframe in ["1Min", "5Min"] else 40)

    try:
        if is_crypto:
            req = CryptoBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=_tf(timeframe),
                start=start,
                end=end,
                limit=limit,
            )
            bars = crypto_data.get_crypto_bars(req).df
        else:
            req = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=_tf(timeframe),
                start=start,
                end=end,
                limit=limit,
                feed=DataFeed.IEX,  # free feed
            )
            bars = stock_data.get_stock_bars(req).df

        if bars.empty:
            return pd.DataFrame()

        if isinstance(bars.index, pd.MultiIndex):
            bars = bars.loc[symbol]

        bars = bars.reset_index()
        # Normalize column names
        bars.columns = [c.lower() for c in bars.columns]
        if "timestamp" in bars.columns:
            bars = bars.rename(columns={"timestamp": "time"})
        bars["time"] = pd.to_datetime(bars["time"])
        return bars.tail(limit).reset_index(drop=True)

    except Exception as e:
        print(f"[data] Error fetching {symbol} {timeframe}: {e}")
        return pd.DataFrame()


def get_news(symbols: list[str], hours: int = 18) -> list[dict]:
    """Fetch recent news for symbols."""
    try:
        from alpaca.data.historical.news import NewsClient
        news_client = NewsClient(API_KEY, SECRET_KEY)

        start = datetime.utcnow() - timedelta(hours=hours)
        req = NewsRequest(
            symbols=",".join([s.replace("/USD", "") for s in symbols if "/" not in s][:5]),
            start=start,
            limit=30,
        )
        news = news_client.get_news(req)
        results = []
        for n in news:
            results.append({
                "headline": n.headline,
                "summary": getattr(n, "summary", "") or "",
                "created_at": n.created_at,
                "symbols": n.symbols or [],
                "url": n.url,
            })
        return results
    except Exception as e:
        print(f"[data] News error: {e}")
        return []


def submit_market_order(symbol: str, qty: float, side: str):
    """Submit a simple market order (paper)."""
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce

    side_enum = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
    is_crypto = "/" in symbol

    order_data = MarketOrderRequest(
        symbol=symbol,
        qty=round(qty, 6) if is_crypto else int(qty),
        side=side_enum,
        time_in_force=TimeInForce.GTC if is_crypto else TimeInForce.DAY,
    )
    return trading_client.submit_order(order_data)


def close_position(symbol: str):
    try:
        trading_client.close_position(symbol)
        return True
    except Exception as e:
        print(f"[data] Close error {symbol}: {e}")
        return False