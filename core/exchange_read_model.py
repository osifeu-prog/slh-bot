"""Read-only exchange truth model.

Aggregates the existing exchange order/trade state without mutating it.
No order placement, cancellation, settlement, or balance changes.
"""
from decimal import Decimal, InvalidOperation


SYMBOL = "SLH/CREDITS"


def _dec(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def _orders(db):
    raw = db.get("exchange_orders", {})
    values = list(raw.values()) if isinstance(raw, dict) else (raw if isinstance(raw, list) else [])
    return [o for o in values if isinstance(o, dict)]


def _trades(db):
    raw = db.get("exchange_trades", [])
    return [t for t in raw if isinstance(t, dict)] if isinstance(raw, list) else []


def _book(orders):
    bids = []
    asks = []
    for o in orders:
        if o.get("status") != "open":
            continue
        row = {
            "id": o.get("id"),
            "amount": o.get("remaining_amount", o.get("original_amount")),
            "price": o.get("limit_price"),
            "created_at": o.get("created_at"),
        }
        if o.get("side") == "buy":
            bids.append(row)
        elif o.get("side") == "sell":
            asks.append(row)
    bids.sort(key=lambda x: (-_dec(x.get("price")), x.get("created_at") or ""))
    asks.sort(key=lambda x: (_dec(x.get("price")), x.get("created_at") or ""))
    return bids, asks


def _levels(rows):
    levels = {}
    for row in rows:
        price = str(row.get("price"))
        amount = _dec(row.get("amount"))
        levels[price] = levels.get(price, Decimal("0")) + amount
    result = [{"price": price, "amount": format(amount, "f")} for price, amount in levels.items()]
    result.sort(key=lambda x: _dec(x["price"]))
    return result


def get_exchange_snapshot(db, trade_limit=100):
    orders = _orders(db)
    trades = _trades(db)
    bids, asks = _book(orders)

    recent = trades[-max(1, int(trade_limit)):]
    prices = [_dec(t.get("price")) for t in trades if _dec(t.get("price")) > 0]
    volume = sum((_dec(t.get("slh_amount")) for t in recent), Decimal("0"))

    last = recent[-1] if recent else None
    last_price = _dec(last.get("price")) if last else Decimal("0")
    high = max((_dec(t.get("price")) for t in recent), default=Decimal("0"))
    low = min((_dec(t.get("price")) for t in recent), default=Decimal("0"))

    return {
        "symbol": SYMBOL,
        "read_only": True,
        "market": {
            "status": "ACTIVE" if orders or trades else "EMPTY",
            "order_count": sum(1 for o in orders if o.get("status") == "open"),
            "trade_count": len(trades),
        },
        "ticker": {
            "has_data": bool(last),
            "last_price": format(last_price, "f") if last else None,
            "high_recent": format(high, "f") if recent else None,
            "low_recent": format(low, "f") if recent else None,
            "volume_slh_recent": format(volume, "f"),
            "last_trade_at": last.get("timestamp") if last else None,
        },
        "orderbook": {
            "best_bid": bids[0] if bids else None,
            "best_ask": asks[0] if asks else None,
            "bids": _levels(bids),
            "asks": _levels(asks),
        },
        "trades": [
            {
                "id": t.get("id"),
                "slh_amount": t.get("slh_amount"),
                "price": t.get("price"),
                "credits_value": t.get("credits_value"),
                "timestamp": t.get("timestamp"),
            }
            for t in recent
        ],
    }
