"""One-time, paper-only SOL/USD test order for AURORA.

This script is intentionally separate from auto_trader.py. The fixed client_order_id
makes repeated manual workflow runs idempotent: an existing order is reported, not
submitted again.
"""
import os
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

API_KEY = os.getenv("ALPACA_API_KEY", "").strip()
API_SECRET = os.getenv("ALPACA_SECRET_KEY", "").strip()
ORDER_ID = "aurora-one-time-sol10-paper-test-v1"

def main():
    if os.getenv("AURORA_ONE_TIME_TEST", "").strip().lower() != "true":
        raise SystemExit("Safety stop: AURORA_ONE_TIME_TEST must be true.")
    if not API_KEY or not API_SECRET:
        raise SystemExit("Missing Alpaca API credentials.")

    # Explicitly use Alpaca paper endpoint; never instantiate a live client.
    client = TradingClient(API_KEY, API_SECRET, paper=True)
    account = client.get_account()
    status = str(getattr(account, "status", "")).lower()
    if not status.endswith("active") or getattr(account, "trading_blocked", False):
        raise SystemExit(f"Paper account is not active/tradable (status={status}).")
    if float(getattr(account, "buying_power", 0) or 0) < 10:
        raise SystemExit("Paper account has less than $10 buying power.")

    try:
        existing = client.get_order_by_client_id(ORDER_ID)
    except Exception as exc:
        # Only a confirmed not-found response permits submission. Any other lookup
        # error stops the run to avoid risking a duplicate.
        status_code = getattr(exc, "status_code", None)
        if status_code != 404:
            raise
        existing = None

    if existing is not None:
        print(f"TEST ORDER ALREADY EXISTS; no new order submitted. id={existing.id} status={existing.status}")
        return

    asset = client.get_asset("SOL/USD")
    if not getattr(asset, "tradable", False):
        raise SystemExit("SOL/USD is not marked tradable by Alpaca.")

    request = MarketOrderRequest(
        symbol="SOL/USD",
        notional=10.00,
        side=OrderSide.BUY,
        time_in_force=TimeInForce.GTC,
        client_order_id=ORDER_ID,
    )
    order = client.submit_order(order_data=request)
    print("PAPER TEST ORDER SUBMITTED")
    print(f"symbol={order.symbol} side={order.side} notional=$10.00")
    print(f"order_id={order.id} client_order_id={order.client_order_id} status={order.status}")
    print("Submission is not the same as a fill; check order status in Alpaca.")

if __name__ == "__main__":
    main()
