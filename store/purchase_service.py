import json
from datetime import datetime, timezone

import state_manager
from store.engine import load_items
from core.economy_bridge import get_balance, spend
from store.grant_engine import apply_grant

LEDGER_FILE = "state/rewards_ledger.json"


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


def _get_or_create_purchase(uid, item_id, request_id, item):
    price = item.get("price", 0)
    if not isinstance(price, (int, float)) or price < 0:
        return None, "NEGATIVE_PRICE" if isinstance(price, (int, float)) else "INVALID_REQUEST"

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
        return True, {
            "status": "ALREADY_COMPLETED",
            "item": purchase_state["item_name"],
            "paid": purchase_state["price"],
            "grant": purchase_state.get("fulfillment"),
        }

    if status == "CREATED":
        if get_balance(uid) < purchase_state["price"]:
            _release_reservation(purchase_state["purchase_id"])
            _update_purchase(purchase_state["purchase_id"], status="REJECTED", error="NOT_ENOUGH_SLH")
            return False, "NOT_ENOUGH_SLH"

        result = spend(
            uid,
            purchase_state["price"],
            reason="store:purchase",
            meta={
                "idempotency_key": purchase_state["purchase_id"] + ":debit",
                "purchase_id": purchase_state["purchase_id"],
                "item_id": item_id,
            },
        )
        if result is False:
            _release_reservation(purchase_state["purchase_id"])
            _update_purchase(purchase_state["purchase_id"], status="REJECTED", error="PAYMENT_FAILED")
            return False, "PAYMENT_FAILED"

        purchase_state = _update_purchase(purchase_state["purchase_id"], status="CHARGED")

    if status not in ("CREATED", "RECOVERABLE", "FULFILLING", "CHARGED"):
        return False, "INVALID_PURCHASE_STATE"

    purchase_state = _update_purchase(purchase_state["purchase_id"], status="FULFILLING")
    try:
        fulfillment = apply_grant(uid, item.get("grant", {}), purchase_id=purchase_state["purchase_id"])
        if not fulfillment or (isinstance(fulfillment, dict) and fulfillment.get("ok") is False):
            raise RuntimeError("FULFILLMENT_FAILED")
    except Exception as exc:
        _update_purchase(purchase_state["purchase_id"], status="RECOVERABLE", error=str(exc))
        return False, "RECOVERABLE"

    purchase_state = _update_purchase(
        purchase_state["purchase_id"],
        status="FULFILLED",
        fulfillment=fulfillment,
        fulfilled_at=datetime.now(timezone.utc).isoformat(),
        error=None,
    )
    _record_compat_ledger(purchase_state, fulfillment)

    return True, {
        "status": "SUCCESS",
        "item": purchase_state["item_name"],
        "paid": purchase_state["price"],
        "grant": fulfillment,
        "commission": 0,
    }
