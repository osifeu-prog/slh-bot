"""Retry-safe store purchase workflow.

Credits are always debited through EconomyService. Store fulfillment is a
separate, retryable state transition so an external/hardware failure cannot
silently turn a successful payment into a lost entitlement.
"""

import json
import uuid
from datetime import datetime, timezone

import state_manager
from core import economy_service
from store.engine import load_items

LEDGER_FILE = "state/rewards_ledger.json"


def load_ledger():
    try:
        with open(LEDGER_FILE, encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return []


def save_ledger(data):
    with open(LEDGER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _apply_digital_grant(user, grant):
    if "permission" in grant:
        permissions = user.setdefault("permissions", [])
        value = grant["permission"]
        if value not in permissions:
            permissions.append(value)
        return {"type": "permission", "value": value}
    if "course" in grant:
        user.setdefault("academy", {})["active_course"] = grant["course"]
        return {"type": "course", "value": grant["course"]}
    if "digital" in grant:
        inventory = user.setdefault("inventory", {})
        items = inventory.setdefault("digital", [])
        value = grant["digital"]
        if value not in items:
            items.append(value)
        return {"type": "digital", "value": value}
    return None


def _reserve(db, uid, item_id, item, purchase_key):
    users = db.setdefault("users", {})
    if uid not in users:
        raise ValueError("USER_NOT_FOUND")

    purchases = db.setdefault("store_purchases", {})
    existing = purchases.get(purchase_key)
    if existing:
        return existing

    price = float(item.get("price", 0) or 0)
    if price < 0:
        raise ValueError("INVALID_PRICE")

    now = datetime.now(timezone.utc).isoformat()
    order = {
        "purchase_key": purchase_key,
        "user_id": uid,
        "item_id": item_id,
        "item": item.get("name", item_id),
        "amount": price,
        "grant": item.get("grant") or {},
        "status": "payment_pending",
        "created_at": now,
    }
    purchases[purchase_key] = order
    return order


def _mark(db, purchase_key, **fields):
    current = db.setdefault("store_purchases", {}).get(purchase_key)
    if not current:
        return {"status": "blocked", "reason": "ORDER_NOT_FOUND"}
    if current.get("status") == "completed":
        return current
    current.update(fields)
    return current


def purchase(uid, item_id, request_id=None):
    uid = str(uid)
    item_id = str(item_id).strip()
    request_id = str(request_id or uuid.uuid4().hex)
    purchase_key = f"store:{uid}:{request_id}"
    items = load_items()

    if item_id not in items:
        return False, "ITEM_NOT_FOUND"

    item = items[item_id]
    price = float(item.get("price", 0) or 0)
    if price < 0:
        return False, "INVALID_PRICE"

    try:
        order = state_manager.atomic_update(
            lambda db: _reserve(db, uid, item_id, item, purchase_key)
        )
    except ValueError as exc:
        return False, str(exc)
    except Exception:
        return False, "ORDER_FAILED"

    if order.get("status") == "completed":
        return True, order

    if order.get("status") not in {"paid", "pending_fulfillment"}:
        try:
            balance_after = economy_service.record_transaction(
                uid,
                -price,
                reason=f"purchase:{item_id}",
                meta={"idempotency_key": purchase_key, "item_id": item_id},
            )
        except Exception as exc:
            state_manager.atomic_update(
                lambda db: _mark(
                    db, purchase_key,
                    status="payment_failed",
                    last_error=type(exc).__name__,
                )
            )
            return False, "NOT_ENOUGH_SLH" if type(exc).__name__ == "ValueError" else "PAYMENT_FAILED"

        order = state_manager.atomic_update(
            lambda db: _mark(
                db,
                purchase_key,
                status="paid",
                paid_at=datetime.now(timezone.utc).isoformat(),
                balance_after=balance_after,
            )
        )

    if order.get("status") == "completed":
        return True, order

    def fulfill(db):
        current = db.setdefault("store_purchases", {}).get(purchase_key)
        if not current:
            return {"status": "blocked", "reason": "ORDER_NOT_FOUND"}
        if current.get("status") == "completed":
            return current

        grant = current.get("grant") or {}
        uid_local = current["user_id"]
        user = db["users"][uid_local]

        if "hardware" in grant:
            existing_grant = current.get("grant_result") or {}
            existing_order_id = existing_grant.get("order_id")
            if existing_order_id:
                hw_order = db.setdefault("hardware_orders", {}).get(existing_order_id)
                if hw_order and hw_order.get("status") == "completed":
                    current["status"] = "completed"
                    current["completed_at"] = datetime.now(timezone.utc).isoformat()
                else:
                    current["status"] = "pending_fulfillment"
                return current

            if current.get("status") not in {"paid", "pending_fulfillment"}:
                return current

            hw_id = str(grant["hardware"])
            product = db.setdefault("products", {}).get(hw_id)
            if not isinstance(product, dict):
                current["status"] = "pending_fulfillment"
                current["last_error"] = "HARDWARE_PRODUCT_NOT_FOUND"
                return current
            inventory = int(product.get("inventory", 0) or 0)
            if inventory <= 0:
                current["status"] = "pending_fulfillment"
                current["last_error"] = "OUT_OF_STOCK"
                return current
            product["inventory"] = inventory - 1
            order_id = f"HW-{uuid.uuid4().hex}"
            db.setdefault("hardware_orders", {})[order_id] = {
                "order_id": order_id,
                "uid": uid_local,
                "item_id": current["item_id"],
                "hardware": hw_id,
                "status": "pending_fulfillment",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            current["grant_result"] = {"type": "hardware", "order_id": order_id, "status": "pending_fulfillment"}
            current["status"] = "pending_fulfillment"
            return current

        if current.get("status") != "paid":
            return current
        current["grant_result"] = _apply_digital_grant(user, grant)
        current["status"] = "completed"
        current["completed_at"] = datetime.now(timezone.utc).isoformat()
        return current

    result = state_manager.atomic_update(fulfill)
    return True, result
