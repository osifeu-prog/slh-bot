"""Canonical housekeeping for retiring internal exchange test/seed state.

Only records explicitly classified as test/seed are archived. Live customer
orders and trades are not selected merely because they are old.
"""

from __future__ import annotations

from datetime import datetime, timezone
import re

import state_manager
from core.audit import log_event



_TEST_SEED_RE = re.compile(
    r"(?<![A-Za-z0-9])(test|seed|genesis)(?![A-Za-z0-9])",
    re.IGNORECASE,
)


def is_test_seed(record) -> bool:
    if not isinstance(record, dict):
        return False
    for key in ("test", "is_test", "seed", "is_seed"):
        if record.get(key) is True:
            return True

    def walk(value):
        if isinstance(value, dict):
            for nested in value.values():
                yield from walk(nested)
        elif isinstance(value, (list, tuple, set)):
            for nested in value:
                yield from walk(nested)
        elif isinstance(value, str):
            yield value

    return any(_TEST_SEED_RE.search(value or "") for value in walk(record))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def preview() -> dict:
    db = state_manager.load_db()
    orders = db.get("exchange_orders", {}) or {}
    trades = db.get("exchange_trades", []) or []
    selected_trades = [t for t in trades if is_test_seed(t)]
    trade_ids = {str(t.get("id")) for t in selected_trades}

    selected_orders = []
    for oid, order in orders.items():
        if not isinstance(order, dict):
            continue
        linked = {
            str(order.get("id")),
            str(order.get("buy_order_id")),
            str(order.get("sell_order_id")),
        }
        if is_test_seed(order) or linked.intersection(trade_ids):
            selected_orders.append(order)

    return {
        "test_seed_trades": len(selected_trades),
        "test_seed_orders": len(selected_orders),
        "trade_ids": sorted(x for x in trade_ids if x and x != "None"),
        "order_ids": sorted(str(o.get("id")) for o in selected_orders if o.get("id")),
    }


def archive_test_state(actor_uid: str) -> dict:
    actor_uid = str(actor_uid)
    before = preview()
    if not before["test_seed_trades"] and not before["test_seed_orders"]:
        return {"archived_trades": 0, "archived_orders": 0, "backup": None}

    db_before = state_manager.load_db()
    from handlers.exchange_handler import _assert_invariants
    _assert_invariants(db_before)
    for oid in before["order_ids"]:
        order = (db_before.get("exchange_orders", {}) or {}).get(oid)
        if isinstance(order, dict) and order.get("status") == "open":
            raise ValueError("EXCHANGE_TEST_ORDER_OPEN_CANNOT_ARCHIVE")

    backup = state_manager.backup_db()

    def mutate(db):
        orders = db.setdefault("exchange_orders", {})
        trades = db.setdefault("exchange_trades", [])
        trade_archive = db.setdefault("exchange_trade_archive", [])
        order_archive = db.setdefault("exchange_order_archive", {})

        selected_trades = [t for t in trades if _is_test_seed(t)]
        selected_trade_ids = {str(t.get("id")) for t in selected_trades}

        selected_orders = []
        for oid, order in list(orders.items()):
            if not isinstance(order, dict):
                continue
            linked = {
                str(order.get("id")),
                str(order.get("buy_order_id")),
                str(order.get("sell_order_id")),
            }
            if _is_test_seed(order) or linked.intersection(selected_trade_ids):
                selected_orders.append((str(oid), order))

        archived_at = _now()
        for trade in selected_trades:
            item = dict(trade)
            item.update({
                "archived_at": archived_at,
                "archived_by": actor_uid,
                "archive_reason": "test_seed_retirement",
            })
            trade_archive.append(item)

        for oid, order in selected_orders:
            item = dict(order)
            item.update({
                "archived_at": archived_at,
                "archived_by": actor_uid,
                "archive_reason": "test_seed_retirement",
            })
            order_archive[oid] = item
            orders.pop(oid, None)

        db["exchange_trades"] = [t for t in trades if not _is_test_seed(t)]

        return {
            "archived_trades": len(selected_trades),
            "archived_orders": len(selected_orders),
        }

    result = state_manager.atomic_update(mutate)
    log_event(
        "exchange_test_state_archived",
        actor=actor_uid,
        details={
            "archived_trades": result["archived_trades"],
            "archived_orders": result["archived_orders"],
            "reason": "test_seed_retirement",
            "backup": backup,
        },
    )
    return {**result, "backup": backup}
