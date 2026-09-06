"""Authoritative store purchase path.

Money, entitlement and purchase state for digital products are committed in
one state_manager.atomic_update. Hardware purchases are durable pending
fulfillment records because external provisioning is not a filesystem
transaction.
"""

import json
import uuid
from datetime import datetime, timezone

import state_manager
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


def purchase(uid, item_id, request_id=None):
    uid = str(uid)
    item_id = str(item_id).strip()
    request_id = str(request_id or uuid.uuid4().hex)
    items = load_items()

    if item_id not in items:
        return False, "ITEM_NOT_FOUND"

    item = items[item_id]
    price = float(item.get("price", 0) or 0)
    if price < 0:
        return False, "INVALID_PRICE"

    grant = item.get("grant") or {}
    purchase_key = f"store:{uid}:{request_id}"

    def mutate(db):
        users = db.setdefault("users", {})
        user = users.get(uid)
        if user is None:
            raise ValueError("USER_NOT_FOUND")

        purchases = db.setdefault("store_purchases", {})
        existing = purchases.get(purchase_key)
        if existing:
            return existing

        wallet = user.setdefault("wallet", {})
        before = float(wallet.get("credits", 0) or 0)
        if before < price:
            raise ValueError("NOT_ENOUGH_SLH")

        # Validate inventory before charging so an invalid hardware order never
        # consumes customer credits.
        hardware_order_id = None
        if "hardware" in grant:
            hw_id = str(grant["hardware"])
            product = db.setdefault("products", {}).get(hw_id)
            if not isinstance(product, dict):
                raise ValueError("HARDWARE_PRODUCT_NOT_FOUND")
            inventory = int(product.get("inventory", 0) or 0)
            if inventory <= 0:
                raise ValueError("OUT_OF_STOCK")
            product["inventory"] = inventory - 1
            hardware_order_id = f"HW-{uuid.uuid4().hex}"

        after = before - price
        wallet["credits"] = after

        commission = 0.0
        referrer_uid = user.get("referral", {}).get("referred_by")
        if referrer_uid and str(referrer_uid) != uid and str(referrer_uid) in users:
            commission = round(price * 0.85, 2)
            ref_user = users[str(referrer_uid)]
            ref_wallet = ref_user.setdefault("wallet", {})
            ref_before = float(ref_wallet.get("credits", 0) or 0)
            ref_wallet["credits"] = ref_before + commission

        now = datetime.now(timezone.utc).isoformat()
        ledger = db.setdefault("ledger", [])
        ledger.append({
            "time": now,
            "uid": uid,
            "before": before,
            "amount": -price,
            "after": after,
            "reason": f"purchase:{item_id}",
            "meta": {"idempotency_key": purchase_key, "item_id": item_id},
        })

        if commission > 0:
            ledger.append({
                "time": now,
                "uid": str(referrer_uid),
                "before": ref_before,
                "amount": commission,
                "after": ref_before + commission,
                "reason": "referral:commission",
                "meta": {"purchase_item": item_id, "source_uid": uid, "purchase_key": purchase_key},
            })

        result = {
            "purchase_key": purchase_key,
            "user_id": uid,
            "item": item.get("name", item_id),
            "item_id": item_id,
            "amount": price,
            "grant": None,
            "commission": commission,
            "timestamp": now,
            "status": "completed",
        }

        if hardware_order_id:
            db.setdefault("hardware_orders", {})[hardware_order_id] = {
                "order_id": hardware_order_id,
                "uid": uid,
                "item_id": item_id,
                "hardware": str(grant["hardware"]),
                "status": "pending_fulfillment",
                "created_at": now,
            }
            result["grant"] = {"type": "hardware", "order_id": hardware_order_id, "status": "pending_fulfillment"}
            result["status"] = "pending_fulfillment"
        else:
            result["grant"] = _apply_digital_grant(user, grant)

        purchases[purchase_key] = result
        return result

    try:
        result = state_manager.atomic_update(mutate)
    except ValueError as exc:
        reason = str(exc)
        return False, reason if reason in {"USER_NOT_FOUND", "NOT_ENOUGH_SLH", "OUT_OF_STOCK", "HARDWARE_PRODUCT_NOT_FOUND", "INVALID_PRICE"} else "PAYMENT_FAILED"
    except Exception:
        return False, "PAYMENT_FAILED"

    return True, result
