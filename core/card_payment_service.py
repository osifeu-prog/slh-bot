"""PayPlus card checkout authority.

Card payments are deliberately restricted to physical/hardware products.
Telegram digital goods/credits remain Stars-only inside Telegram.

No card charge is created unless CARD_PAYMENTS_OPEN=1 and all PayPlus
credentials + a per-item ILS price are configured.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import time
import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

import requests

import state_manager
from core import revenue_ledger
from store.engine import load_items, resolve_item_id
from store.grant_engine import apply_grant

PAYPLUS_PROD = "https://restapi.payplus.co.il/api/v1.0"
PAYPLUS_STAGING = "https://restapidev.payplus.co.il/api/v1.0"


def _enabled() -> bool:
    return os.getenv("CARD_PAYMENTS_OPEN", "0").strip() == "1"


def _api_base() -> str:
    env = os.getenv("PAYPLUS_ENV", "production").strip().lower()
    return (PAYPLUS_STAGING if env in {"staging", "test"} else PAYPLUS_PROD).rstrip("/")


def _public_base() -> str:
    return os.getenv("CARD_PAYMENTS_PUBLIC_BASE_URL", "").strip().rstrip("/")


def _configured() -> bool:
    return bool(
        os.getenv("PAYPLUS_PAYMENT_PAGE_UID", "").strip()
        and os.getenv("PAYPLUS_API_KEY", "").strip()
        and os.getenv("PAYPLUS_SECRET_KEY", "").strip()
        and _public_base()
    )


def card_payments_status() -> dict:
    return {
        "enabled": _enabled(),
        "configured": _configured(),
        "environment": os.getenv("PAYPLUS_ENV", "production").strip().lower(),
        "public_base_configured": bool(_public_base()),
    }


def _price_env_key(item_id: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", str(item_id).strip()).strip("_").upper()
    return f"SLH_CARD_PRICE_ILS_{normalized}"


def get_card_price_ils(item_id: str) -> Decimal | None:
    raw = os.getenv(_price_env_key(item_id), "").strip()
    if not raw:
        return None
    try:
        price = Decimal(raw).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None
    return price if price > 0 else None


def get_card_items() -> list[dict]:
    items = load_items()
    result = []
    for item_id, item in items.items():
        if not isinstance(item, dict):
            continue
        # Card path is deliberately physical/hardware-only.
        if str(item.get("type", "")).strip().lower() != "hardware":
            continue
        price = get_card_price_ils(item_id)
        if price is None:
            continue
        result.append({
            "id": str(item_id),
            "name": str(item.get("name", item_id)),
            "price_ils": float(price),
            "currency": "ILS",
            "type": "hardware",
        })
    result.sort(key=lambda row: (row["price_ils"], row["name"]))
    return result


def _require_card_config():
    if not _enabled():
        raise RuntimeError("CARD_PAYMENTS_CLOSED")
    if not _configured():
        raise RuntimeError("CARD_PROVIDER_NOT_CONFIGURED")


def _json_headers() -> dict[str, str]:
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "api-key": os.getenv("PAYPLUS_API_KEY", "").strip(),
        "secret-key": os.getenv("PAYPLUS_SECRET_KEY", "").strip(),
    }


def _post_payplus(path: str, payload: dict) -> dict:
    url = f"{_api_base()}/{path.lstrip('/')}"
    response = requests.post(url, headers=_json_headers(), json=payload, timeout=25)
    try:
        data = response.json()
    except ValueError:
        data = {"raw": response.text[:1000]}
    if response.status_code >= 400:
        raise RuntimeError(f"PAYPLUS_HTTP_{response.status_code}")
    if not isinstance(data, dict):
        raise RuntimeError("PAYPLUS_INVALID_RESPONSE")
    return data


def _extract_value(obj: Any, keys: set[str]) -> Any:
    if isinstance(obj, dict):
        for key in keys:
            if key in obj and obj[key] not in (None, ""):
                return obj[key]
        for value in obj.values():
            found = _extract_value(value, keys)
            if found not in (None, ""):
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = _extract_value(value, keys)
            if found not in (None, ""):
                return found
    return None


def _all_dicts(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _all_dicts(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _all_dicts(value)


def _money(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return None


def _find_tx_summary(data: dict) -> dict:
    """Extract only transaction-level approval data from PayPlus API variants."""
    success_words = {
        "success", "successful", "approved", "approve", "paid", "completed",
        "complete", "succeeded", "ok", "true",
    }
    candidates = []
    statuses = set()

    for row in _all_dicts(data):
        tx_uid = row.get("transaction_uid") or row.get("transactionUid")
        amount = row.get("amount") or row.get("transaction_amount") or row.get("total_amount")
        currency = row.get("currency_code") or row.get("currency")
        approved_flags = [
            row.get(key) for key in ("approved", "success", "paid")
            if isinstance(row.get(key), bool)
        ]
        row_statuses = {
            str(row.get(key)).strip().lower()
            for key in ("status", "transaction_status", "payment_status", "state")
            if row.get(key) not in (None, "")
        }
        if not (tx_uid or amount or currency):
            continue

        statuses.update(row_statuses)
        candidates.append({
            "transaction_uid": str(tx_uid).strip() if tx_uid else None,
            "amount": _money(amount),
            "currency": str(currency).strip().upper() if currency else None,
            "approved": any(approved_flags) or any(s in success_words for s in row_statuses),
        })

    tx = next((c for c in candidates if c["transaction_uid"] and c["approved"]), None)
    if tx is None:
        tx = next((c for c in candidates if c["transaction_uid"]), None)

    return {
        "approved": bool(tx and tx.get("approved")),
        "statuses": sorted(statuses),
        "transaction_uid": (tx or {}).get("transaction_uid"),
        "amount": (tx or {}).get("amount"),
        "currency": (tx or {}).get("currency"),
        "raw": data,
    }


def _validate_callback(body: dict, supplied_hash: str, user_agent: str) -> bool:
    secret = os.getenv("PAYPLUS_SECRET_KEY", "").strip()
    if not secret or not supplied_hash or user_agent != "PayPlus":
        return False
    compact = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    expected = base64.b64encode(
        hmac.new(secret.encode("utf-8"), compact, hashlib.sha256).digest()
    ).decode("ascii")
    return hmac.compare_digest(str(supplied_hash).strip(), expected)


def _find_order(order_id: str | None = None, page_request_uid: str | None = None) -> dict | None:
    db = state_manager.load_db()
    orders = db.get("card_orders", {})
    if not isinstance(orders, dict):
        return None
    if order_id and isinstance(orders.get(order_id), dict):
        return dict(orders[order_id])
    if page_request_uid:
        for row in orders.values():
            if isinstance(row, dict) and str(row.get("page_request_uid", "")) == str(page_request_uid):
                return dict(row)
    return None


def _update_order(order_id: str, **changes) -> dict:
    def mutate(db):
        order = db.setdefault("card_orders", {}).get(order_id)
        if not order:
            raise KeyError("CARD_ORDER_NOT_FOUND")
        order.update(changes)
        return dict(order)
    return state_manager.atomic_update(mutate)


def _find_existing_request(uid: str, client_request_id: str) -> dict | None:
    if not client_request_id:
        return None
    db = state_manager.load_db()
    orders = db.get("card_orders", {})
    if not isinstance(orders, dict):
        return None
    for row in orders.values():
        if (
            isinstance(row, dict)
            and str(row.get("uid")) == str(uid)
            and str(row.get("client_request_id")) == client_request_id
            and row.get("status") not in {"FAILED", "CANCELLED"}
        ):
            return dict(row)
    return None


def create_card_checkout(uid: str, item_id: str, client_request_id: str | None = None) -> dict:
    _require_card_config()
    uid = str(uid).strip()
    item_id = str(resolve_item_id(item_id, load_items()) or "").strip()
    if not uid:
        raise ValueError("INVALID_USER_ID")
    if not item_id:
        raise ValueError("ITEM_NOT_FOUND")

    items = load_items()
    item = items.get(item_id)
    if not isinstance(item, dict):
        raise ValueError("ITEM_NOT_FOUND")
    if str(item.get("type", "")).strip().lower() != "hardware":
        raise ValueError("CARD_ONLY_PHYSICAL_PRODUCTS")

    price = get_card_price_ils(item_id)
    if price is None:
        raise ValueError("CARD_ITEM_PRICE_NOT_CONFIGURED")

    client_request_id = str(client_request_id or "").strip()
    if client_request_id:
        existing = _find_existing_request(uid, client_request_id)
        if existing and existing.get("payment_page_link"):
            return existing

    order_id = f"card:{uuid.uuid4().hex}"
    record = {
        "order_id": order_id,
        "uid": uid,
        "item_id": item_id,
        "item_name": str(item.get("name", item_id)),
        "amount": float(price),
        "currency": "ILS",
        "provider": "payplus",
        "status": "CREATED",
        "client_request_id": client_request_id or None,
        "page_request_uid": None,
        "payment_page_link": None,
        "transaction_uid": None,
        "created_at": time.time(),
        "updated_at": time.time(),
        "fulfillment": None,
        "error": None,
    }

    def create_record(db):
        db.setdefault("card_orders", {})[order_id] = record
        return dict(record)

    state_manager.atomic_update(create_record)

    base = _public_base()
    generate_payload = {
        "payment_page_uid": os.getenv("PAYPLUS_PAYMENT_PAGE_UID", "").strip(),
        "charge_method": 1,
        "amount": float(price),
        "currency_code": "ILS",
        "language_code": "he",
        "allowed_charge_methods": ["credit-card", "apple-pay", "google-pay"],
        "more_info": order_id,
        "refURL_success": f"{base}/card-pay/success?order_id={order_id}",
        "refURL_failure": f"{base}/card-pay/failure?order_id={order_id}",
        "refURL_cancel": f"{base}/card-pay/cancel?order_id={order_id}",
        "refURL_callback": f"{base}/api/card-pay/callback",
        "send_failure_callback": True,
        "items": [{
            "name": str(item.get("name", item_id)),
            "price": float(price),
            "quantity": 1,
        }],
    }

    try:
        result = _post_payplus("PaymentPages/generateLink", generate_payload)
        data = result.get("data") if isinstance(result.get("data"), dict) else {}
        page_uid = data.get("page_request_uid") or data.get("page_requestUID") or data.get("payment_request_uid")
        link = data.get("payment_page_link") or data.get("payment_page_url") or data.get("link")
        if not page_uid or not link:
            raise RuntimeError("PAYPLUS_LINK_MISSING")
        return _update_order(
            order_id,
            status="LINK_CREATED",
            page_request_uid=str(page_uid),
            payment_page_link=str(link),
            updated_at=time.time(),
        )
    except Exception as exc:
        _update_order(
            order_id,
            status="FAILED",
            error=type(exc).__name__,
            updated_at=time.time(),
        )
        raise


def _verify_provider_transaction(order: dict, callback_body: dict) -> dict:
    page_uid = str(order.get("page_request_uid") or "").strip()
    transaction_uid = str(
        _extract_value(callback_body, {"transaction_uid", "transactionUid"})
        or ""
    ).strip()
    lookup: dict
    if page_uid:
        lookup = {"payment_request_uid": page_uid}
    elif transaction_uid:
        lookup = {"transaction_uid": transaction_uid}
    else:
        raise ValueError("PAYPLUS_TRANSACTION_REFERENCE_MISSING")

    verified = _post_payplus("PaymentPages/ipn-full", lookup)
    summary = _find_tx_summary(verified)
    if not summary["approved"]:
        raise ValueError("PAYPLUS_PAYMENT_NOT_APPROVED")

    amount = summary.get("amount")
    currency = summary.get("currency")
    expected_amount = _money(order.get("amount"))
    if amount is not None and expected_amount is not None and amount != expected_amount:
        raise ValueError("PAYPLUS_AMOUNT_MISMATCH")
    if currency and currency != "ILS":
        raise ValueError("PAYPLUS_CURRENCY_MISMATCH")

    tx_uid = summary.get("transaction_uid") or transaction_uid
    if not tx_uid:
        raise ValueError("PAYPLUS_TRANSACTION_UID_MISSING")
    return {
        "transaction_uid": str(tx_uid),
        "verified": True,
        "provider_response": verified,
        "summary": summary,
    }


def _notify(uid: str, text: str):
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": str(uid), "text": str(text)},
            timeout=10,
        )
    except Exception:
        pass


def _fulfill(order: dict) -> dict:
    order_id = str(order["order_id"])
    if order.get("status") == "FULFILLED":
        return {"status": "duplicate", "order": order}

    def claim(db):
        current = db.setdefault("card_orders", {}).get(order_id)
        if not current:
            raise KeyError("CARD_ORDER_NOT_FOUND")
        if current.get("status") == "FULFILLED":
            return dict(current), "DUPLICATE"
        if current.get("status") == "FULFILLING":
            started = float(current.get("fulfillment_started_at", 0) or 0)
            if started and time.time() - started < 15 * 60:
                return dict(current), "IN_PROGRESS"
        current["status"] = "FULFILLING"
        current["fulfillment_started_at"] = time.time()
        current["updated_at"] = time.time()
        current["error"] = None
        return dict(current), "CLAIMED"

    claimed, claim_status = state_manager.atomic_update(claim)
    if claim_status == "DUPLICATE":
        return {"status": "duplicate", "order": claimed}
    if claim_status == "IN_PROGRESS":
        return {"status": "in_progress", "order": claimed}

    order = claimed
    item = load_items().get(str(order["item_id"]))
    if not isinstance(item, dict):
        raise ValueError("ITEM_NOT_FOUND")

    try:
        fulfillment = apply_grant(
            str(order["uid"]),
            item.get("grant", {}),
            purchase_id=order_id,
        )
        if not fulfillment or (isinstance(fulfillment, dict) and fulfillment.get("ok") is False):
            raise RuntimeError("FULFILLMENT_FAILED")

        fulfilled = _update_order(
            order_id,
            status="FULFILLED",
            fulfillment=fulfillment,
            fulfilled_at=time.time(),
            updated_at=time.time(),
            error=None,
        )
        revenue_ledger.record(
            source="payplus_card",
            amount=float(order["amount"]),
            currency="ILS",
            reference=str(order.get("transaction_uid") or order_id),
            uid=str(order["uid"]),
            meta={
                "order_id": order_id,
                "item_id": order["item_id"],
                "provider": "payplus",
            },
        )
        _notify(
            str(order["uid"]),
            "✅ תשלום בכרטיס אומת בהצלחה וההזמנה שלך סופקה.\n"
            f"מוצר: {order['item_name']}\n"
            f"סכום: {order['amount']:.2f} ILS",
        )
        return {"status": "fulfilled", "order": fulfilled}
    except Exception as exc:
        failed = _update_order(
            order_id,
            status="RECOVERABLE",
            error=type(exc).__name__,
            fulfillment_started_at=None,
            updated_at=time.time(),
        )
        _notify(
            str(order["uid"]),
            "⚠️ התשלום נקלט, אבל אספקת המוצר ממתינה לניסיון אוטומטי נוסף.\n"
            "לא בוצע חיוב נוסף. ניתן לבדוק /card_orders.",
        )
        return {"status": "recoverable", "order": failed}


def handle_payplus_callback(body: dict, supplied_hash: str, user_agent: str) -> dict:
    _require_card_config()
    if not _validate_callback(body, supplied_hash, user_agent):
        raise ValueError("PAYPLUS_CALLBACK_INVALID")

    order_id = _extract_value(body, {"more_info", "moreInfo"})
    page_uid = _extract_value(body, {"page_request_uid", "page_requestUID", "payment_request_uid"})
    order = _find_order(str(order_id) if order_id else None, str(page_uid) if page_uid else None)
    if not order:
        raise ValueError("CARD_ORDER_NOT_FOUND")

    if order.get("status") == "FULFILLED":
        return {"status": "duplicate", "order_id": order["order_id"]}

    verification = _verify_provider_transaction(order, body)
    updated = _update_order(
        order["order_id"],
        status="PAID",
        transaction_uid=verification["transaction_uid"],
        provider_response=verification["provider_response"],
        updated_at=time.time(),
        error=None,
    )
    return _fulfill(updated)


def reconcile_card_orders(limit: int = 20, uid: str | None = None) -> dict:
    """Recover card orders even when the provider callback was delayed or lost.

    LINK_CREATED orders are re-checked with PayPlus by payment_request_uid.
    PAID/RECOVERABLE orders only retry fulfillment. No new charge is created.
    """
    if not _enabled() or not _configured():
        return {"attempted": 0, "success": 0, "remaining": 0, "skipped": True}

    db = state_manager.load_db()
    orders = db.get("card_orders", {})
    if not isinstance(orders, dict):
        return {"attempted": 0, "success": 0, "remaining": 0}

    now = time.time()
    pending = []
    for row in orders.values():
        if not isinstance(row, dict):
            continue
        if uid is not None and str(row.get("uid")) != str(uid):
            continue
        status = str(row.get("status", ""))
        if status not in {"LINK_CREATED", "PAID", "RECOVERABLE"}:
            continue
        if status == "LINK_CREATED":
            try:
                created_at = float(row.get("created_at", now) or now)
            except (TypeError, ValueError):
                created_at = now
            if now - created_at > 48 * 3600:
                continue
        pending.append(dict(row))

    attempted = success = 0
    for order in pending[:max(0, int(limit))]:
        attempted += 1
        try:
            current = order
            if current.get("status") == "LINK_CREATED":
                page_uid = str(current.get("page_request_uid") or "").strip()
                if not page_uid:
                    continue
                verified = _post_payplus(
                    "PaymentPages/ipn-full",
                    {"payment_request_uid": page_uid},
                )
                summary = _find_tx_summary(verified)
                if not summary.get("approved"):
                    continue

                amount = summary.get("amount")
                expected_amount = _money(current.get("amount"))
                if amount is not None and expected_amount is not None and amount != expected_amount:
                    _update_order(
                        current["order_id"],
                        status="RECOVERABLE",
                        error="PAYPLUS_AMOUNT_MISMATCH",
                        updated_at=time.time(),
                    )
                    continue

                currency = summary.get("currency")
                if currency and currency != "ILS":
                    _update_order(
                        current["order_id"],
                        status="RECOVERABLE",
                        error="PAYPLUS_CURRENCY_MISMATCH",
                        updated_at=time.time(),
                    )
                    continue

                tx_uid = str(summary.get("transaction_uid") or "").strip()
                if not tx_uid:
                    continue

                current = _update_order(
                    current["order_id"],
                    status="PAID",
                    transaction_uid=tx_uid,
                    provider_response=verified,
                    updated_at=time.time(),
                    error=None,
                )

            result = _fulfill(current)
            if result.get("status") in {"fulfilled", "duplicate"}:
                success += 1
        except Exception as exc:
            print("[CARD] automatic reconciliation error:", type(exc).__name__)

    return {
        "attempted": attempted,
        "success": success,
        "remaining": max(0, len(pending) - success),
    }


def start_card_recovery_loop(interval_seconds: int = 300):
    """Run provider reconciliation + fulfillment recovery in the background."""
    import threading

    interval_seconds = max(60, int(interval_seconds))

    def runner():
        time.sleep(15)
        while True:
            try:
                result = reconcile_card_orders(limit=20)
                if result.get("attempted"):
                    print("[CARD] automatic reconciliation:", result)
            except Exception as exc:
                print("[CARD] reconciliation loop error:", type(exc).__name__)
            time.sleep(interval_seconds)

    thread = threading.Thread(
        target=runner,
        daemon=True,
        name="card-payment-recovery",
    )
    thread.start()
    return thread


def recover_card_orders(uid: str, limit: int = 10) -> dict:
    uid = str(uid)
    db = state_manager.load_db()
    orders = db.get("card_orders", {})
    pending = [
        dict(row)
        for row in orders.values()
        if isinstance(row, dict)
        and str(row.get("uid")) == uid
        and row.get("status") in {"PAID", "RECOVERABLE"}
    ] if isinstance(orders, dict) else []

    attempted = success = 0
    for order in pending[:max(0, int(limit))]:
        attempted += 1
        result = _fulfill(order)
        if result.get("status") in {"fulfilled", "duplicate"}:
            success += 1

    return {"attempted": attempted, "success": success, "remaining": max(0, len(pending) - success)}
