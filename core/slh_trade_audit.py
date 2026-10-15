"""Read-only, trade-level SLH exchange settlement audit.

The audit consumes a caller-supplied DB snapshot and never mutates it.
It validates trade/order links and settlement ledger evidence; it does not
claim to reconstruct historical wallet balances when snapshots are unavailable.
"""
from decimal import Decimal, InvalidOperation

TRADE_KEY = "exchange_trades"
ORDER_KEYS = ("exchange_orders", "exchange_order_archive")
CREDITS_LEDGER_KEY = "ledger"
SLH_LEDGER_KEY = "slh_token_ledger"
_SCALE = Decimal("0.00000001")


def _decimal(value):
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def _close(left, right):
    a, b = _decimal(left), _decimal(right)
    return a is not None and b is not None and abs(a - b) <= _SCALE


def _meta(row):
    value = row.get("meta")
    return value if isinstance(value, dict) else {}


def _order_rows(db):
    orders = {}
    for key in ORDER_KEYS:
        source = db.get(key)
        if source is None:
            continue
        if isinstance(source, dict):
            rows = source.items()
        elif isinstance(source, list):
            rows = ((str(i), item) for i, item in enumerate(source))
        else:
            return None
        for row_key, row in rows:
            if not isinstance(row, dict):
                continue
            oid = str(row.get("order_id") or row.get("id") or row_key)
            orders[oid] = row
    return orders


def audit_trades(db, trade_ids):
    """Return a per-trade PASS/FAIL/UNKNOWN report from an existing DB snapshot."""
    requested = [str(value) for value in trade_ids]
    if not isinstance(db, dict):
        return {"status": "UNKNOWN", "trades": [
            {"trade_id": tid, "status": "UNKNOWN", "checks": {"snapshot": None}}
            for tid in requested
        ]}
    trades = db.get(TRADE_KEY)
    orders = _order_rows(db)
    credits = db.get(CREDITS_LEDGER_KEY)
    slh_ledger = db.get(SLH_LEDGER_KEY)
    source_unknown = (
        not isinstance(trades, list) or orders is None
        or not isinstance(credits, list) or not isinstance(slh_ledger, list)
    )
    trade_map = {
        str(row.get("id")): row for row in trades
        if isinstance(row, dict) and row.get("id") is not None
    } if isinstance(trades, list) else {}

    reports = []
    for tid in requested:
        if source_unknown:
            reports.append({
                "trade_id": tid, "status": "UNKNOWN",
                "checks": {"snapshot_sources": None},
            })
            continue
        matching_trades = [
            row for row in trades
            if isinstance(row, dict) and str(row.get("id")) == tid
        ]
        trade = matching_trades[0] if matching_trades else None
        if trade is None:
            reports.append({
                "trade_id": tid, "status": "FAIL",
                "checks": {"trade_record": False},
            })
            continue

        checks = {"trade_record_unique": len(matching_trades) == 1}
        buyer_uid = str(trade.get("buyer_uid") or "")
        seller_uid = str(trade.get("seller_uid") or "")
        amount = _decimal(trade.get("slh_amount"))
        price = _decimal(trade.get("price"))
        value = _decimal(trade.get("credits_value"))
        checks["trade_fields"] = bool(
            buyer_uid and seller_uid and buyer_uid != seller_uid
            and amount is not None and amount > 0
            and price is not None and price > 0
            and value is not None and value >= 0
        )
        checks["credits_value_math"] = (
            _close(value, amount * price)
            if checks["trade_fields"] else False
        )

        buy_id = str(trade.get("buy_order_id") or "")
        sell_id = str(trade.get("sell_order_id") or "")
        buy_order, sell_order = orders.get(buy_id), orders.get(sell_id)
        checks["orders_exist"] = bool(buy_order and sell_order and buy_id != sell_id)
        if checks["orders_exist"]:
            checks["order_sides_and_parties"] = bool(
                str(buy_order.get("side") or "").lower() == "buy"
                and str(sell_order.get("side") or "").lower() == "sell"
                and str(buy_order.get("uid") or buy_order.get("user_id") or "") == buyer_uid
                and str(sell_order.get("uid") or sell_order.get("user_id") or "") == seller_uid
            )
            bid = _decimal(buy_order.get("limit_price"))
            ask = _decimal(sell_order.get("limit_price"))
            checks["trade_price_within_bid"] = (
                price is not None and bid is not None and price <= bid
            )
            checks["trade_price_within_ask"] = (
                price is not None and ask is not None and price >= ask
            )
        else:
            checks["order_sides_and_parties"] = False
            checks["trade_price_within_bid"] = False
            checks["trade_price_within_ask"] = False

        event_id = f"exchange:settlement_slh:{tid}"
        settlement_rows = [
            row for row in slh_ledger
            if isinstance(row, dict) and str(row.get("event_id") or "") == event_id
        ]
        if len(settlement_rows) != 1:
            checks["slh_settlement_event_unique"] = False
            checks["slh_settlement_matches_trade"] = False
        else:
            row = settlement_rows[0]
            checks["slh_settlement_event_unique"] = True
            checks["slh_settlement_matches_trade"] = bool(
                row.get("kind") == "exchange_settlement"
                and str(row.get("trade_id") or "") == tid
                and str(row.get("order_id") or "") == sell_id
                and str(row.get("seller_uid") or "") == seller_uid
                and str(row.get("to_uid") or "") == buyer_uid
                and str(row.get("from_uid") or "") == "__EXCHANGE_RESERVE__"
                and _close(row.get("amount"), amount)
            )

        seller_credit_rows = [
            row for row in credits
            if isinstance(row, dict)
            and str(row.get("reason") or "") == "exchange:settlement_credits"
            and str(_meta(row).get("trade_id") or "") == tid
        ]
        checks["seller_credits_event_unique"] = len(seller_credit_rows) == 1
        checks["seller_credits_match_trade"] = bool(
            len(seller_credit_rows) == 1
            and str(seller_credit_rows[0].get("uid") or "") == seller_uid
            and _close(seller_credit_rows[0].get("amount"), value)
            and str(_meta(seller_credit_rows[0]).get("order_id") or "") == sell_id
        )

        improvement = None
        if checks["orders_exist"]:
            bid = _decimal(buy_order.get("limit_price"))
            if bid is not None and price is not None and amount is not None:
                improvement = max(Decimal("0"), amount * (bid - price))
        if improvement is None:
            checks["buyer_price_improvement"] = None
        elif improvement == 0:
            refunds = [
                row for row in credits
                if isinstance(row, dict)
                and str(row.get("reason") or "") == "exchange:price_improvement_release"
                and str(_meta(row).get("trade_id") or "") == tid
            ]
            checks["buyer_price_improvement"] = len(refunds) == 0
        else:
            refunds = [
                row for row in credits
                if isinstance(row, dict)
                and str(row.get("reason") or "") == "exchange:price_improvement_release"
                and str(_meta(row).get("trade_id") or "") == tid
            ]
            checks["buyer_price_improvement"] = bool(
                len(refunds) == 1
                and str(refunds[0].get("uid") or "") == buyer_uid
                and _close(refunds[0].get("amount"), improvement)
                and str(_meta(refunds[0]).get("order_id") or "") == buy_id
            )

        values = list(checks.values())
        status = "UNKNOWN" if any(value is None for value in values) else (
            "PASS" if all(value is True for value in values) else "FAIL"
        )
        reports.append({"trade_id": tid, "status": status, "checks": checks})

    statuses = [row["status"] for row in reports]
    overall = "FAIL" if "FAIL" in statuses else "UNKNOWN" if "UNKNOWN" in statuses else "PASS"
    return {"status": overall, "trades": reports}
