"""Retry-safe marketplace purchase workflow.

Marketplace fulfillment is a filesystem side effect, while credits are owned
by EconomyService. The order is reserved first, the debit is idempotent, and
fulfillment is finalized only after installation succeeds.
"""

import time
import uuid

import state_manager
from core import economy_service
from plugins_store import install_plugin


def purchase_plugin(uid, plugin, request_id=None):
    uid = str(uid)
    plugin_id = str(plugin.get("id", "")).strip()
    price = float(plugin.get("price", 0) or 0)
    request_id = str(request_id or uuid.uuid4().hex)
    purchase_key = f"market:{uid}:{request_id}"

    if not plugin_id:
        return False, "PLUGIN_NOT_FOUND"
    if price < 0:
        return False, "INVALID_PRICE"

    def reserve(db):
        if uid not in db.setdefault("users", {}):
            raise ValueError("USER_NOT_FOUND")
        orders = db.setdefault("marketplace_orders", {})
        existing = orders.get(purchase_key)
        if existing:
            return existing

        order = {
            "order_id": f"MKT-{uuid.uuid4().hex}",
            "purchase_key": purchase_key,
            "uid": uid,
            "plugin_id": plugin_id,
            "price": price,
            "status": "payment_pending",
            "created_at": time.time(),
        }
        orders[purchase_key] = order
        return order

    try:
        order = state_manager.atomic_update(reserve)
    except ValueError as exc:
        return False, str(exc)
    except Exception:
        return False, "ORDER_FAILED"

    if order.get("status") == "completed":
        return True, order

    try:
        credits = economy_service.record_transaction(
            uid,
            -price,
            reason="marketplace:purchase",
            meta={
                "idempotency_key": purchase_key,
                "plugin_id": plugin_id,
                "order_id": order["order_id"],
            },
        )
    except Exception as exc:
        def mark_payment_failed(db):
            current = db.setdefault("marketplace_orders", {}).get(purchase_key)
            if current and current.get("status") != "completed":
                current["status"] = "payment_failed"
                current["last_error"] = type(exc).__name__
                current["last_attempt_at"] = time.time()
            return current or {"status": "blocked", "reason": "ORDER_NOT_FOUND"}

        state_manager.atomic_update(mark_payment_failed)
        return False, "PAYMENT_FAILED"

    def mark_fulfillment_pending(db):
        current = db.setdefault("marketplace_orders", {}).get(purchase_key)
        if not current:
            return {"status": "blocked", "reason": "ORDER_NOT_FOUND"}
        current["status"] = "pending_fulfillment"
        current["debited_at"] = time.time()
        current["balance_after"] = credits
        return current

    order = state_manager.atomic_update(mark_fulfillment_pending)
    if order.get("status") == "completed":
        return True, order

    try:
        install_result = install_plugin(plugin_id)
    except Exception as exc:
        install_result = f"installation error: {type(exc).__name__}"

    success = isinstance(install_result, str) and "installed successfully" in install_result.lower()

    def finalize(db):
        current = db.setdefault("marketplace_orders", {}).get(purchase_key)
        if not current:
            return {"status": "blocked", "reason": "ORDER_NOT_FOUND"}
        if current.get("status") == "completed":
            return current
        if success:
            current["status"] = "completed"
            current["fulfilled_at"] = time.time()
            current["install_result"] = install_result
        else:
            current["status"] = "pending_fulfillment"
            current["last_error"] = install_result
            current["last_attempt_at"] = time.time()
        return current

    result = state_manager.atomic_update(finalize)
    if result.get("status") != "completed":
        return True, {**result, "message": "Payment recorded; plugin fulfillment pending"}

    return True, {**result, "message": install_result}
