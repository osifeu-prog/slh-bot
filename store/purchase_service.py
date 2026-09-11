import json
from datetime import datetime, timezone, timedelta

import state_manager
from store.engine import load_items
from core.economy_bridge import get_balance, spend
from store.grant_engine import apply_grant

LEDGER_FILE = "state/rewards_ledger.json"
FULFILLMENT_STALE_SECONDS = 15 * 60


def load_ledger():
    try:
        return json.load(open(LEDGER_FILE, encoding="utf-8-sig"))
    except Exception:
        return []


def save_ledger(data):
    with open(LEDGER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _purchase_id(request_id):
    return "purchase:" + str(request_id)


def _validate_item(item):
    price = item.get("price", 0)
    if isinstance(price, bool) or not isinstance(price, (int, float)) or price < 0:
        return "NEGATIVE_PRICE" if isinstance(price, (int, float)) and not isinstance(price, bool) and price < 0 else "INVALID_REQUEST"
    grant = item.get("grant")
    if not isinstance(grant, dict) or not grant:
        return "UNSUPPORTED_GRANT"
    if not any(key in grant for key in ("permission", "course", "digital", "hardware")):
        return "UNSUPPORTED_GRANT"
    return None


def _get_or_create_purchase(uid, item_id, request_id, item):
    error = _validate_item(item)
    if error:
        return None, error
    price = item.get("price", 0)
    purchase_id = _purchase_id(request_id)

    def mutate(db):
        purchases = db.setdefault("purchases", {})
        existing = purchases.get(purchase_id)
        if existing:
            if str(existing.get("request_id")) != str(request_id) or str(existing.get("uid")) != str(uid) or existing.get("item_id") != item_id:
                return None, "REQUEST_ID_CONFLICT"
            return existing, None

        reservation = None
        if item.get("type") == "hardware":
            products = db.setdefault("products", {})
            product = products.get(item_id)
            inventory = int(product.get("inventory", 0)) if product else 0
            if product is None or inventory <= 0:
                return None, "OUT_OF_STOCK"
            product["inventory"] = inventory - 1
            reservation = {"item_id": item_id, "quantity": 1}

        purchase = {
            "purchase_id": purchase_id,
            "request_id": str(request_id),
            "uid": str(uid),
            "item_id": item_id,
            "item_name": item.get("name", item_id),
            "price": price,
            "status": "CREATED",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "inventory_reservation": reservation,
            "fulfillment": None,
            "fulfillment_started_at": None,
            "ledger_recorded": False,
        }
        purchases[purchase_id] = purchase
        return purchase, None

    return state_manager.atomic_update(mutate)


def _update_purchase(purchase_id, **changes):
    def mutate(db):
        purchase = db.setdefault("purchases", {}).get(purchase_id)
        if not purchase:
            raise KeyError("PURCHASE_NOT_FOUND")
        purchase.update(changes)
        return purchase
    return state_manager.atomic_update(mutate)


def _claim_fulfillment(purchase_id):
    now = datetime.now(timezone.utc)
    def mutate(db):
        purchase = db.setdefault("purchases", {}).get(purchase_id)
        if not purchase:
            raise KeyError("PURCHASE_NOT_FOUND")
        status = purchase.get("status")
        if status == "FULFILLING":
            started = purchase.get("fulfillment_started_at")
            try:
                started_at = datetime.fromisoformat(started) if started else None
            except Exception:
                started_at = None
            if started_at and (now - started_at).total_seconds() < FULFILLMENT_STALE_SECONDS:
                return None, "IN_PROGRESS"
        if status not in ("CREATED", "CHARGED", "RECOVERABLE", "FULFILLING"):
            return None, "INVALID_PURCHASE_STATE"
        purchase["status"] = "FULFILLING"
        purchase["fulfillment_started_at"] = now.isoformat()
        return purchase, None
    return state_manager.atomic_update(mutate)


def _release_reservation(purchase_id):
    def mutate(db):
        purchase = db.setdefault("purchases", {}).get(purchase_id)
        if not purchase or not purchase.get("inventory_reservation"):
            return False
        item_id = purchase["inventory_reservation"]["item_id"]
        product = db.setdefault("products", {}).get(item_id)
        if product is not None:
            product["inventory"] = int(product.get("inventory", 0)) + 1
        purchase["inventory_reservation"] = None
        return True
    return state_manager.atomic_update(mutate)


def _record_compat_ledger(purchase, fulfillment):
    if purchase.get("ledger_recorded"):
        return
    ledger = load_ledger()
    if any(entry.get("purchase_id") == purchase["purchase_id"] for entry in ledger):
        _update_purchase(purchase["purchase_id"], ledger_recorded=True)
        return
    ledger.append({
        "purchase_id": purchase["purchase_id"],
        "user_id": purchase["uid"],
        "item": purchase["item_id"],
        "amount": purchase["price"],
        "grant": fulfillment,
        "commission": 0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    save_ledger(ledger)
    _update_purchase(purchase["purchase_id"], ledger_recorded=True)


def purchase(uid, item_id, request_id=None):
    if request_id is None:
        request_id = f"legacy:{uid}:{item_id}"
    uid = str(uid)
    item_id = str(item_id).strip()
    items = load_items()
    if item_id not in items:
        return False, "ITEM_NOT_FOUND"

    item = items[item_id]
    purchase_state, error = _get_or_create_purchase(uid, item_id, request_id, item)
    if error:
        return False, error
    if purchase_state is None:
        return False, "INVALID_REQUEST"

    status = purchase_state.get("status")
    if status == "FULFILLED":
        return True, {"status": "ALREADY_COMPLETED", "item": purchase_state["item_name"], "paid": purchase_state["price"], "grant": purchase_state.get("fulfillment")}
    if status == "REJECTED":
        return False, purchase_state.get("error", "PURCHASE_REJECTED")

    if status == "CREATED":
        if get_balance(uid) < purchase_state["price"]:
            _release_reservation(purchase_state["purchase_id"])
            _update_purchase(purchase_state["purchase_id"], status="REJECTED", error="NOT_ENOUGH_SLH")
            return False, "NOT_ENOUGH_SLH"
        try:
            result = spend(uid, purchase_state["price"], reason="store:purchase", meta={"idempotency_key": purchase_state["purchase_id"] + ":debit", "purchase_id": purchase_state["purchase_id"], "item_id": item_id})
        except Exception:
            _release_reservation(purchase_state["purchase_id"])
            _update_purchase(purchase_state["purchase_id"], status="REJECTED", error="PAYMENT_FAILED")
            return False, "PAYMENT_FAILED"
        if result is False:
            _release_reservation(purchase_state["purchase_id"])
            _update_purchase(purchase_state["purchase_id"], status="REJECTED", error="PAYMENT_FAILED")
            return False, "PAYMENT_FAILED"
        purchase_state = _update_purchase(purchase_state["purchase_id"], status="CHARGED")

    claim, claim_error = _claim_fulfillment(purchase_state["purchase_id"])
    if claim_error:
        if claim_error == "IN_PROGRESS":
            return False, "IN_PROGRESS"
        return False, claim_error

    try:
        fulfillment = apply_grant(uid, item.get("grant", {}), purchase_id=claim["purchase_id"])
        if not fulfillment or (isinstance(fulfillment, dict) and fulfillment.get("ok") is False):
            raise RuntimeError("FULFILLMENT_FAILED")
    except Exception as exc:
        _update_purchase(claim["purchase_id"], status="RECOVERABLE", error=type(exc).__name__, fulfillment_started_at=None)
        return False, "RECOVERABLE"

    purchase_state = _update_purchase(claim["purchase_id"], status="FULFILLED", fulfillment=fulfillment, fulfilled_at=datetime.now(timezone.utc).isoformat(), fulfillment_started_at=None, error=None)
    _record_compat_ledger(purchase_state, fulfillment)
    return True, {"status": "SUCCESS", "item": purchase_state["item_name"], "paid": purchase_state["price"], "grant": fulfillment, "commission": 0}
