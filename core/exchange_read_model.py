"""Exchange read model for the SLH Truth Layer.

Read-only. Aggregates exchange state for any consumer (Mini App, Telegram, Web).
No mutation. No order creation. No balance changes.
"""

import json
from pathlib import Path


def _load_db():
    try:
        return json.loads(Path("state/db.json").read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def get_exchange_summary():
    db = _load_db()
    orders = db.get("exchange_orders", {}) or {}
    trades = db.get("exchange_trades", []) or []
    seq = db.get("exchange_sequence", 0)

    open_orders = [o for o in orders.values() if isinstance(o, dict) and o.get("status") == "open"]
    open_orders.sort(key=lambda o: int(o.get("sequence", 0)))
    recent_trades = trades[-20:] if isinstance(trades, list) else []

    last_price = None
    if recent_trades:
        last_price = recent_trades[-1].get("price")

    return {
        "ticker": {
            "last_price": last_price,
            "has_data": last_price is not None,
        },
        "orderbook": {
            "orders": [
                {
                    "id": o.get("id"),
                    "side": o.get("side"),
                    "amount": o.get("remaining_amount"),
                    "price": o.get("limit_price"),
                    "uid": o.get("uid"),
                }
                for o in open_orders[:50]
            ]
        },
        "trades": {
            "trades": [
                {
                    "id": t.get("id"),
                    "buyer_uid": t.get("buyer_uid"),
                    "seller_uid": t.get("seller_uid"),
                    "slh_amount": t.get("slh_amount"),
                    "price": t.get("price"),
                    "credits_value": t.get("credits_value"),
                }
                for t in recent_trades
            ]
        },
        "status": {
            "open": True,
            "total_orders": len(open_orders),
            "total_trades": len(trades) if isinstance(trades, list) else 0,
            "sequence": seq,
        },
    }
