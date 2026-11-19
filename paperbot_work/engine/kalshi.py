"""Read-only Kalshi public crypto prediction-market data."""
from datetime import datetime, timezone
import requests

BASE_URL = "https://external-api.kalshi.com/trade-api/v2"
SERIES = {
    "BTC": ["KXBTC15M", "KXBTC"],
    "ETH": ["KXETH15M", "KXETH"],
    "SOL": ["KXSOL15M", "KXSOL"],
    "XRP": ["KXXRP15M", "KXXRP"],
}
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "OrochiQuantTerminal/1.0"})


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fetch_crypto_markets():
    """Fetch open crypto contracts from known series; public read-only endpoints."""
    rows, errors = [], []
    seen = set()
    for coin, series_list in SERIES.items():
        for series in series_list:
            try:
                response = SESSION.get(
                    f"{BASE_URL}/markets",
                    params={"series_ticker": series, "status": "open", "limit": 100},
                    timeout=8,
                )
                if response.status_code == 404:
                    continue
                response.raise_for_status()
                for market in response.json().get("markets", []):
                    ticker = market.get("ticker")
                    if not ticker or ticker in seen:
                        continue
                    seen.add(ticker)
                    yes_bid = _number(market.get("yes_bid_dollars"))
                    yes_ask = _number(market.get("yes_ask_dollars"))
                    last = _number(market.get("last_price_dollars"))
                    if yes_bid is not None and yes_ask is not None and yes_ask >= yes_bid:
                        probability, source = (yes_bid + yes_ask) / 2, "YES bid/ask midpoint"
                    elif last is not None:
                        probability, source = last, "last traded YES price"
                    elif yes_bid is not None:
                        probability, source = yes_bid, "YES bid only"
                    else:
                        probability, source = None, "no quote"
                    rows.append({
                        "COIN": coin,
                        "MARKET": market.get("title") or market.get("subtitle") or ticker,
                        "TICKER": ticker,
                        "YES PROBABILITY": probability,
                        "QUOTE SOURCE": source,
                        "VOLUME 24H": _number(market.get("volume_24h_fp")),
                        "CLOSE TIME": market.get("close_time") or market.get("expected_expiration_time") or "—",
                        "UPDATED UTC": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                    })
            except Exception as exc:
                errors.append(f"{series}: {type(exc).__name__}")
    return rows, errors
