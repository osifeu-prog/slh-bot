"""Telegram Stars store authority: payment idempotency, fulfillment, revenue."""
from datetime import datetime, timezone

import state_manager
from store.engine import load_items
from store.grant_engine import apply_grant
from core import revenue_ledger


def _now():
    return datetime.now(timezone.utc).isoformat()


def get_stars_price(item_id):
    item = load_items().get(str(item_id).strip())
    if not isinstance(item, dict):
        return None
    value = item.get("price_stars")
    if isinstance(value, bool):
        return None
    try:
        value = int(value)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def get_stars_items():
    items = load_items()
    return {
        item_id: int(item["price_stars"])
        for item_id, item in items.items()
        if isinstance(item, dict)
        and not isinstance(item.get("price_stars"), bool)
        and str(item.get("price_stars", "")).isdigit()
        and int(item["price_stars"]) > 0
    }


def _update_order(order_id, **changes):
    def mutate(db):
        order = db.setdefault("star_item_orders", {}).get(order_id)
        if not order:
            raise KeyError("STAR_ORDER_NOT_FOUND")
        order.update(changes)
        return order

    return state_manager.atomic_update(mutate)


def _release_reservation(order_id):
    def mutate(db):
        order = db.setdefault("star_item_orders", {}).get(order_id)
        if not order or not order.get("inventory_reservation"):
            return False
        item_id = order["inventory_reservation"]["item_id"]
        product = db.setdefault("products", {}).get(item_id)
        if product is not None:
            product["inventory"] = int(product.get("inventory", 0)) + int(order["inventory_reservation"].get("quantity", 1))
        order["inventory_reservation"] = None
        return True
    return state_manager.atomic_update(mutate)


def purchase_item_with_stars(uid, item_id, stars_paid, charge_id):
    uid = str(uid)
    item_id = str(item_id).strip()
    charge_id = str(charge_id or "").strip()

    if not charge_id:
        raise ValueError("INVALID_CHARGE_ID")

    expected_stars = get_stars_price(item_id)
    if expected_stars is None:
        raise ValueError("ITEM_NOT_AVAILABLE_FOR_STARS")

    try:
        stars_paid = int(stars_paid)
    except (TypeError, ValueError) as exc:
        raise ValueError("INVALID_STARS_AMOUNT") from exc
    if stars_paid != expected_stars:
        raise ValueError("INVALID_STARS_AMOUNT")

    items = load_items()
    item = items.get(item_id)
    if not isinstance(item, dict):
        raise ValueError("ITEM_NOT_FOUND")

    order_id = "stars:" + charge_id

    def create_order(db):
        users = db.setdefault("users", {})
        if uid not in users:
            raise ValueError("USER_NOT_FOUND")

        orders = db.setdefault("star_item_orders", {})
        existing = orders.get(order_id)
        if existing:
            return existing

        reservation = None
        if item.get("type") == "hardware":
            products = db.setdefault("products", {})
            product = products.get(item_id)
            inventory = int(product.get("inventory", 0)) if product else 0
            if product is None or inventory <= 0:
                raise ValueError("OUT_OF_STOCK")
            product["inventory"] = inventory - 1
            reservation = {"item_id": item_id, "quantity": 1}

        order = {
            "order_id": order_id,
            "charge_id": charge_id,
            "uid": uid,
            "item_id": item_id,
            "item_name": item.get("name", item_id),
            "stars_paid": stars_paid,
            "status": "PAID",
            "created_at": _now(),
            "inventory_reservation": reservation,
            "fulfillment": None,
        }
        orders[order_id] = order
        return order

    order = state_manager.atomic_update(create_order)
    if order.get("status") == "FULFILLED":
        return {"status": "DUPLICATE", "order_id": order_id, "item_id": item_id}

    try:
        fulfillment = apply_grant(uid, item.get("grant", {}), purchase_id=order_id)
        if not fulfillment or fulfillment.get("ok") is False:
            raise RuntimeError("FULFILLMENT_FAILED")
    except Exception as exc:
        _release_reservation(order_id)
        _update_order(
            order_id,
            status="RECOVERABLE",
            error=type(exc).__name__,
            fulfillment_error=True,
        )
        return {"status": "RECOVERABLE", "order_id": order_id, "item_id": item_id}

    def finalize(db):
        orders = db.setdefault("star_item_orders", {})
        current = orders.get(order_id)
        if not current:
            raise ValueError("STAR_ORDER_NOT_FOUND")
        if current.get("status") == "FULFILLED":
            return current

        current.update({
            "status": "FULFILLED",
            "fulfillment": fulfillment,
            "fulfilled_at": _now(),
            "error": None,
        })

        revenue = db.setdefault("revenue", {"stars_gross": 0, "items": {}, "orders": 0})
        revenue["stars_gross"] = int(revenue.get("stars_gross", 0)) + stars_paid
        revenue["orders"] = int(revenue.get("orders", 0)) + 1
        item_revenue = revenue.setdefault("items", {}).setdefault(item_id, {"orders": 0, "stars": 0})
        item_revenue["orders"] = int(item_revenue.get("orders", 0)) + 1
        item_revenue["stars"] = int(item_revenue.get("stars", 0)) + stars_paid
        return current

    finalized = state_manager.atomic_update(finalize)
    revenue_ledger.record(
        source="telegram_stars_item",
        amount=stars_paid,
        currency="XTR",
        reference=charge_id,
        uid=uid,
        meta={"kind": "telegram_stars_item", "item_id": item_id},
    )
    return {"status": "SUCCESS", "order_id": order_id, "item_id": item_id, "stars": stars_paid, "fulfillment": finalized.get("fulfillment")}
