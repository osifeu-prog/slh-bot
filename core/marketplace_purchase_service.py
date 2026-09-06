"""Retry-safe marketplace purchase workflow.

The credit debit is authoritative in state/db.json. Plugin installation is a
separate filesystem side effect, so purchases are persisted as pending before
external installation and finalized afterward.
"""

import time
import uuid

import state_manager
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
        users = db.setdefault("users", {})
        user = users.get(uid)
        if user is None:
            raise ValueError("USER_NOT_FOUND")
        orders = db.setdefault("marketplace_orders", {})
        if purchase_key in orders:
            return orders[purchase_key]

        wallet = user.setdefault("wallet", {})
        before = float(wallet.get("credits", 0) or 0)
        if before < price:
            raise ValueError("NOT_ENOUGH_CREDITS")

        wallet["credits"] = before - price
        now = time.time()
        order = {
            "order_id": f"MKT-{uuid.uuid4().hex}",
            "purchase_key": purchase_key,
            "uid": uid,
            "plugin_id": plugin_id,
            "price": price,
            "status": "pending_fulfillment",
            "created_at": now,
        }
        orders[purchase_key] = order
        db.setdefault("ledger", []).append({
            "time": now,
            "uid": uid,
            "before": before,
            "amount": -price,
            "after": before - price,
            "reason": "marketplace:purchase",
            "meta": {"idempotency_key": purchase_key, "plugin_id": plugin_id, "order_id": order["order_id"]},
        })
        return order

    try:
        order = state_manager.atomic_update(reserve)
    except ValueError as exc:
        return False, str(exc)
    except Exception:
        return False, "PAYMENT_FAILED"

    if order.get("status") == "completed":
        return True, order

    try:
        install_result = install_plugin(plugin_id)
    except Exception as exc:
        install_result = f"installation error: {type(exc).__name__}"

    success = isinstance(install_result, str) and "installed successfully" in install_result.lower()

    def finalize(db):
        orders = db.setdefault("marketplace_orders", {})
        current = orders.get(purchase_key)
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
