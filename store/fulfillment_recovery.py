"""Safe recovery of already-paid commerce orders.

This module never charges a customer and never moves blockchain funds.
It only retries fulfillment for locally recorded payments that are marked
recoverable/pending.
"""
from __future__ import annotations

import os
import requests
import state_manager


MAX_ATTEMPTS = 20


def reconcile_telegram_stars(limit: int = 100, uid: str | None = None) -> dict:
    """Reconcile recent successful Telegram Stars invoice payments.

    Telegram exposes recent StarTransaction records through getStarTransactions.
    Only incoming user invoice payments are considered. Existing local
    idempotency protects against duplicate processing.
    """
    token = (os.getenv("BOT_TOKEN") or "").strip()
    if not token:
        return {"enabled": False, "attempted": 0, "success": 0, "failed": 0}

    try:
        response = requests.get(
            f"https://api.telegram.org/bot{token}/getStarTransactions",
            params={"limit": max(1, min(int(limit), 100))},
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return {
            "enabled": True,
            "attempted": 0,
            "success": 0,
            "failed": 0,
            "error": type(exc).__name__,
        }

    if not payload.get("ok"):
        return {
            "enabled": True,
            "attempted": 0,
            "success": 0,
            "failed": 0,
            "error": "TELEGRAM_STARS_API_ERROR",
        }

    transactions = (payload.get("result") or {}).get("transactions") or []
    attempted = success = failed = skipped = 0
    details = []

    for tx in transactions:
        if not isinstance(tx, dict):
            skipped += 1
            continue

        try:
            amount = int(tx.get("amount", 0) or 0)
        except (TypeError, ValueError):
            skipped += 1
            continue

        source = tx.get("source") or {}
        if (
            amount <= 0
            or source.get("type") != "user"
            or source.get("transaction_type") != "invoice_payment"
        ):
            skipped += 1
            continue

        user = source.get("user") or {}
        tx_uid = str(user.get("id") or "").strip()
        invoice_payload = str(source.get("invoice_payload") or "").strip()
        charge_id = str(tx.get("id") or "").strip()

        if not tx_uid or not invoice_payload or not charge_id:
            skipped += 1
            continue
        if uid is not None and tx_uid != str(uid):
            continue

        attempted += 1
        try:
            if invoice_payload.startswith("item_") and invoice_payload.endswith("_" + tx_uid):
                item_id = invoice_payload[5:-(len(tx_uid) + 1)]
                from store.stars_purchase_service import purchase_item_with_stars

                result = purchase_item_with_stars(
                    uid=tx_uid,
                    item_id=item_id,
                    stars_paid=amount,
                    charge_id=charge_id,
                )
                ok = result.get("status") in {"SUCCESS", "DUPLICATE"}

            elif invoice_payload == f"vip_monthly_{tx_uid}":
                from core.stars_payment_authority import record_vip_subscription_payment

                result = record_vip_subscription_payment(
                    uid=tx_uid,
                    stars_paid=amount,
                    charge_id=charge_id,
                    recurring=False,
                    first_recurring=True,
                )
                ok = result.get("fulfillment_status") == "completed" or result.get("status") == "duplicate"

            elif invoice_payload.startswith("credits_") and invoice_payload.endswith("_" + tx_uid):
                parts = invoice_payload.split("_")
                if len(parts) != 3 or parts[2] != tx_uid:
                    skipped += 1
                    continue

                try:
                    requested_credits = int(parts[1])
                except (TypeError, ValueError):
                    skipped += 1
                    continue

                from core.stars_price_authority import resolve_credit_pack
                package = resolve_credit_pack(requested_credits, amount)
                if package is None:
                    skipped += 1
                    continue

                from core import stars_payment_authority

                result = stars_payment_authority.record_stars_payment(
                    uid=tx_uid,
                    credits=package.credits,
                    stars_paid=package.stars,
                    currency="XTR",
                    telegram_payment_charge_id=charge_id,
                    provider_payment_charge_id=None,
                    referrer_uid=None,
                    meta={
                        "source": "telegram_star_reconciliation",
                        "invoice_payload": invoice_payload,
                        "reconciled": True,
                    },
                )
                ok = result.get("status") in {"applied", "duplicate"}

            else:
                skipped += 1
                continue

            if ok:
                success += 1
            else:
                failed += 1

            details.append({
                "uid": tx_uid,
                "charge_id": charge_id,
                "payload": invoice_payload[:120],
                "status": result.get("status") or result.get("fulfillment_status"),
            })
        except Exception as exc:
            failed += 1
            details.append({
                "uid": tx_uid,
                "charge_id": charge_id,
                "payload": invoice_payload[:120],
                "status": "error",
                "error": type(exc).__name__,
            })

    return {
        "enabled": True,
        "attempted": attempted,
        "success": success,
        "failed": failed,
        "skipped": skipped,
        "details": details,
    }


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
                stars = reconcile_telegram_stars()
                if stars.get("attempted"):
                    print("[STARS] periodic reconciliation:", stars)
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
