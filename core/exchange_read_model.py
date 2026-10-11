"""Exchange read model for the SLH Truth Layer.

Read-only. Aggregates exchange state and the canonical execution gate for the
Mini App, Telegram and web consumers. It never mutates orders or balances.
"""
from datetime import datetime, timezone


_REQUIRED_DB_TYPES = {
    "users": dict,
    "exchange_orders": dict,
    "exchange_trades": list,
    "exchange_requests": dict,
}


def _load_db():
    """Use the same canonical state loader as execution paths; fail closed on read errors."""
    try:
        import state_manager

        db = state_manager.load_db()
        return db if isinstance(db, dict) else None
    except Exception:
        return None


def _blocked_check(detail):
    return {
        "ok": False,
        "execution_ready": False,
        "public_gate": "CLOSED",
        "verdict": "BLOCKED",
        "public_ready": False,
        "order_book_integrity": False,
        "trade_integrity": False,
        "money_invariants": False,
        "detail": str(detail or "canonical exchange state unavailable")[:300],
    }


def _canonical_execution_check(db):
    if not isinstance(db, dict):
        return _blocked_check("canonical exchange state unreadable")

    invalid = [
        key for key, expected_type in _REQUIRED_DB_TYPES.items()
        if not isinstance(db.get(key), expected_type)
    ]
    if invalid:
        return _blocked_check("canonical exchange state malformed: " + ", ".join(invalid))

    try:
        from core.system_checks import check_exchange_for_execution

        result = check_exchange_for_execution(db)
        if not isinstance(result, dict):
            return _blocked_check("canonical exchange check returned an invalid result")
        return result
    except Exception as exc:
        return _blocked_check(f"canonical exchange check failed: {type(exc).__name__}")


def _status_from_check(check, checked_at, total_orders, total_trades, sequence):
    public_gate = str(check.get("public_gate") or "CLOSED")
    verdict = str(check.get("verdict") or "BLOCKED")
    public_ready = check.get("public_ready") is True
    order_book_integrity = check.get("order_book_integrity") is True
    trade_integrity = check.get("trade_integrity") is True
    money_invariants = check.get("money_invariants") is True
    execution_ready = check.get("execution_ready") is True
    is_open = (
        check.get("ok") is True
        and execution_ready
        and public_gate == "OPEN"
        and verdict == "OPEN"
        and public_ready
        and order_book_integrity
        and trade_integrity
        and money_invariants
    )
    return {
        "open": is_open,
        "public_gate": public_gate if public_gate in {"OPEN", "CLOSED"} else "CLOSED",
        "verdict": "OPEN" if is_open else "BLOCKED",
        "execution_ready": is_open,
        "public_ready": public_ready,
        "order_book_integrity": order_book_integrity,
        "trade_integrity": trade_integrity,
        "money_invariants": money_invariants,
        "checked_at": checked_at,
        "detail": str(check.get("detail") or ("public state clean" if is_open else "fresh Exchange check blocked"))[:300],
        "total_orders": total_orders,
        "total_trades": total_trades,
        "sequence": sequence,
    }


def get_exchange_summary():
    """Return market data plus a fresh, fail-closed canonical execution-gate snapshot."""
    checked_at = datetime.now(timezone.utc).isoformat()
    db = _load_db()
    source_valid = isinstance(db, dict)
    orders_raw = db.get("exchange_orders") if source_valid else None
    trades_raw = db.get("exchange_trades") if source_valid else None
    orders = orders_raw if isinstance(orders_raw, dict) else {}
    trades = trades_raw if isinstance(trades_raw, list) else []
    seq = db.get("exchange_sequence", 0) if source_valid else 0

    open_orders = [
        order for order in orders.values()
        if isinstance(order, dict) and order.get("status") == "open"
    ]
    open_orders.sort(key=lambda order: int(order.get("sequence", 0)))
    bids = [order for order in open_orders if str(order.get("side", "")).lower() == "buy"]
    asks = [order for order in open_orders if str(order.get("side", "")).lower() == "sell"]
    bids.sort(key=lambda order: float(order.get("limit_price", 0)), reverse=True)
    asks.sort(key=lambda order: float(order.get("limit_price", 0)))
    recent_trades = trades[-20:]

    last_price = recent_trades[-1].get("price") if recent_trades else None
    check = _canonical_execution_check(db if source_valid else None)
    status = _status_from_check(check, checked_at, len(open_orders), len(trades), seq)

    return {
        "ticker": {
            "last_price": last_price,
            "has_data": last_price is not None,
        },
        "orderbook": {
            "best_bid": bids[0].get("limit_price") if bids else None,
            "best_ask": asks[0].get("limit_price") if asks else None,
            "orders": [
                {
                    "id": order.get("id"),
                    "side": order.get("side"),
                    "amount": order.get("remaining_amount"),
                    "price": order.get("limit_price"),
                    "uid": order.get("uid"),
                }
                for order in open_orders[:50]
            ],
        },
        "trades": {
            "trades": [
                {
                    "id": trade.get("id"),
                    "buyer_uid": trade.get("buyer_uid"),
                    "seller_uid": trade.get("seller_uid"),
                    "slh_amount": trade.get("slh_amount"),
                    "price": trade.get("price"),
                    "credits_value": trade.get("credits_value"),
                }
                for trade in recent_trades
            ]
        },
        "status": status,
    }
