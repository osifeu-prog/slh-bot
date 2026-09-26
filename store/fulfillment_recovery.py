"""Safe recovery of already-paid commerce orders.

This module never charges a customer and never moves blockchain funds.
It only retries fulfillment for locally recorded payments that are marked
recoverable/pending.
"""
from __future__ import annotations

import state_manager


MAX_ATTEMPTS = 20


def recover_paid_orders(limit: int = MAX_ATTEMPTS, uid: str | None = None) -> dict:
    """Retry pending/recoverable Stars fulfillments, without charging again.

    When uid is supplied, only that customer's orders are retried.
    """
    db = state_manager.load_db()

    star_orders = db.get("star_item_orders") or {}
    vip_orders = db.get("vip_subscriptions") or {}
    candidates = []

    if isinstance(star_orders, dict):
        for order in star_orders.values():
            if not isinstance(order, dict):
                continue
            if order.get("status") in {"RECOVERABLE", "PAID"}:
                if uid is None or str(order.get("uid")) == str(uid):
                    candidates.append(("star", order))

    if isinstance(vip_orders, dict):
        for order in vip_orders.values():
            if not isinstance(order, dict):
                continue
            if order.get("fulfillment_status") in {"pending", "failed"}:
                if uid is None or str(order.get("uid")) == str(uid):
                    candidates.append(("vip", order))

    candidates = candidates[:max(1, int(limit))]
    attempted = success = failed = 0
    details = []

    from store.stars_purchase_service import purchase_item_with_stars
    from core.stars_payment_authority import record_vip_subscription_payment

    for kind, order in candidates:
        attempted += 1
        try:
            if kind == "star":
                result = purchase_item_with_stars(
                    uid=str(order.get("uid")),
                    item_id=str(order.get("item_id")),
                    stars_paid=int(order.get("stars_paid")),
                    charge_id=str(order.get("charge_id")),
                )
                ok = result.get("status") in {"SUCCESS", "DUPLICATE"}
            else:
                result = record_vip_subscription_payment(
                    uid=str(order.get("uid")),
                    stars_paid=int(order.get("stars_paid")),
                    charge_id=str(order.get("charge_id")),
                    recurring=bool(order.get("recurring")),
                    first_recurring=bool(order.get("first_recurring")),
                )
                ok = result.get("fulfillment_status") == "completed"

            if ok:
                success += 1
            else:
                failed += 1
            details.append({
                "kind": kind,
                "charge_id": str(order.get("charge_id")),
                "status": result.get("status") or result.get("fulfillment_status"),
            })
        except Exception as exc:
            failed += 1
            details.append({
                "kind": kind,
                "charge_id": str(order.get("charge_id")),
                "status": "error",
                "error": type(exc).__name__,
            })

    return {
        "attempted": attempted,
        "success": success,
        "failed": failed,
        "details": details,
    }


def start_recovery_loop(interval_seconds: int = 300) -> None:
    """Start a single background retry loop for already-paid fulfillments."""
    import threading
    import time

    if getattr(start_recovery_loop, "_started", False):
        return
    start_recovery_loop._started = True

    def worker():
        while True:
            try:
                result = recover_paid_orders()
                if result.get("attempted"):
                    print("[FULFILLMENT] periodic recovery:", result)
            except Exception as exc:
                print("[FULFILLMENT] periodic recovery error:", type(exc).__name__)
            time.sleep(max(60, int(interval_seconds)))

    threading.Thread(
        target=worker,
        name="slh-fulfillment-recovery",
        daemon=True,
    ).start()
