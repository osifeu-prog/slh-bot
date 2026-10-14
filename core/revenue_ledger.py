"""Revenue observability without inventing cash revenue.

Only record a revenue event when an external payment has actually been
confirmed. Internal Credit spending is not cash revenue and must not be
counted as such.
"""

import math
from datetime import datetime, timezone

import state_manager

KEY = "revenue_ledger"
IMMUTABLE_FIELDS = ("amount", "currency", "uid")


def is_testish(row):
    """Identify known synthetic/legacy test rows without changing the ledger."""
    if not isinstance(row, dict):
        return False
    meta = row.get("meta")
    if not isinstance(meta, dict):
        meta = {}
    if meta.get("test") is True or meta.get("is_test") is True:
        return True
    uid = str(row.get("uid") or "").strip().lower()
    reference = str(
        row.get("reference")
        or row.get("charge_id")
        or row.get("telegram_payment_charge_id")
        or ""
    ).strip().lower()
    return (
        uid.startswith("test")
        or reference.startswith("test")
        or "boundary-test" in reference
        or reference.startswith("fakepay")
    )


def _same_stars_amount(value, expected):
    if isinstance(value, bool):
        return False
    try:
        actual = float(value)
    except (TypeError, ValueError, OverflowError):
        return False
    return math.isfinite(actual) and actual == expected and actual.is_integer()


def _has_xtr_payment_evidence(db, row, amount):
    """Require the source-specific local payment record for an XTR event.

    This deliberately does not call Telegram live APIs. It verifies that the
    revenue row agrees with the persistent transaction/order created by the
    successful-payment handlers. Live reconciliation remains a separate audit.
    """
    reference = str(row.get("reference") or "").strip()
    uid = str(row.get("uid") or "").strip()
    source = str(row.get("source") or "").strip()
    if not reference or not uid or not amount.is_integer():
        return False

    if source == "telegram_stars":
        transactions = db.get("transactions", [])
        transactions = transactions if isinstance(transactions, list) else []
        ledger = db.get("ledger", [])
        tx_match = any(
            isinstance(tx, dict)
            and str(tx.get("telegram_payment_charge_id") or "").strip() == reference
            and str(tx.get("uid") or "").strip() == uid
            and str(tx.get("currency") or "").strip().upper() == "XTR"
            and _same_stars_amount(tx.get("stars_paid"), amount)
            for tx in transactions
        )
        if not tx_match:
            return False
        for event in ledger if isinstance(ledger, list) else []:
            if not isinstance(event, dict):
                continue
            meta = event.get("meta")
            if not isinstance(meta, dict):
                continue
            if event.get("reason") != "payment:telegram_stars":
                continue
            if str(event.get("uid") or "").strip() != uid:
                continue
            if str(meta.get("charge_id") or "").strip() != reference:
                continue
            if str(meta.get("source") or "").strip() != "telegram_successful_payment":
                continue
            if str(meta.get("currency") or "").strip().upper() != "XTR":
                continue
            if bool(meta.get("test_mode")):
                continue
            if not _same_stars_amount(meta.get("stars_paid"), amount):
                continue
            return True
        return False

    if source == "telegram_stars_subscription":
        subscriptions = db.get("vip_subscriptions", {})
        if not isinstance(subscriptions, dict):
            return False
        candidates = [subscriptions.get(reference)]
        candidates.extend(
            value for key, value in subscriptions.items()
            if str(key).strip() != reference
            and isinstance(value, dict)
            and str(value.get("charge_id") or "").strip() == reference
        )
        return any(
            isinstance(item, dict)
            and str(item.get("uid") or "").strip() == uid
            and _same_stars_amount(item.get("stars_paid", item.get("stars")), amount)
            for item in candidates
        )

    if source == "telegram_stars_item":
        orders = db.get("star_item_orders", {})
        if not isinstance(orders, dict):
            return False
        meta = row.get("meta")
        meta = meta if isinstance(meta, dict) else {}
        wanted_item = str(meta.get("item_id") or "").strip()
        # An order reference + amount is not enough to prove which store item
        # was purchased. Missing item metadata must remain unverified.
        if not wanted_item:
            return False
        for item in orders.values():
            if not isinstance(item, dict):
                continue
            if str(item.get("charge_id") or "").strip() != reference:
                continue
            if str(item.get("uid") or "").strip() != uid:
                continue
            if str(item.get("status") or "").strip().upper() not in {
                "PAID", "RECOVERABLE", "FULFILLED"
            }:
                continue
            if not _same_stars_amount(item.get("stars_paid"), amount):
                continue
            if str(item.get("item_id") or "").strip() != wanted_item:
                continue
            return True
        return False

    # Unknown XTR sources must not be described as verified Stars revenue.
    return False


def reportable_rows(db, *, currency=None):
    """Return valid, locally evidenced revenue rows for display only.

    XTR events require a matching payment/commerce record. This is a
    read-only filter: it never modifies the supplied DB or ledger and does
    not substitute for live reconciliation against Telegram.
    """
    rows = db.get(KEY, []) if isinstance(db, dict) else []
    if not isinstance(rows, list):
        return []
    wanted_currency = str(currency).strip().upper() if currency is not None else None
    reportable = []
    for row in rows:
        if not isinstance(row, dict) or is_testish(row):
            continue
        source = str(row.get("source") or "").strip()
        row_currency = str(row.get("currency") or "").strip()
        if not source or not row_currency:
            continue
        if wanted_currency is not None and row_currency.upper() != wanted_currency:
            continue
        raw_amount = row.get("amount", 0)
        if isinstance(raw_amount, bool):
            continue
        try:
            amount = float(raw_amount or 0)
        except (TypeError, ValueError, OverflowError):
            continue
        if not math.isfinite(amount) or amount <= 0:
            continue
        if not str(row.get("reference") or "").strip():
            continue
        if row_currency.upper() == "XTR" and not _has_xtr_payment_evidence(db, row, amount):
            continue
        reportable.append(row)
    return reportable


def _now():
    return datetime.now(timezone.utc).isoformat()


def _build_event(*, source, amount, currency, reference, uid=None, meta=None):
    if not source or not currency or not reference:
        raise ValueError("REVENUE_REFERENCE_REQUIRED")
    if (
        isinstance(amount, bool)
        or not isinstance(amount, (int, float))
        or not math.isfinite(float(amount))
        or float(amount) <= 0
    ):
        raise ValueError("INVALID_REVENUE_AMOUNT")

    return {
        "timestamp": _now(),
        "source": str(source),
        "amount": float(amount),
        "currency": str(currency),
        "reference": str(reference),
        "uid": str(uid) if uid is not None else None,
        "meta": dict(meta or {}),
    }


def _normalized_uid(value):
    return str(value) if value is not None else None


def _conflicting_fields(existing, event):
    """Return immutable fields that disagree for the same source/reference."""
    conflicts = []

    try:
        current_amount = float(existing.get("amount"))
        amount_matches = (
            math.isfinite(current_amount)
            and current_amount == float(event["amount"])
        )
    except (TypeError, ValueError, OverflowError):
        amount_matches = False
    if not amount_matches:
        conflicts.append("amount")

    if str(existing.get("currency") or "") != event["currency"]:
        conflicts.append("currency")

    if _normalized_uid(existing.get("uid")) != event["uid"]:
        conflicts.append("uid")

    return conflicts


def conflicting_fields_in_db(
    db, *, source, amount, currency, reference, uid=None, meta=None
):
    """Read-only preflight for callers that must reject conflicts before mutation.

    Returns an empty list when there is no matching event or the existing
    event matches all immutable fields. This function never changes `db`.
    """
    event = _build_event(
        source=source,
        amount=amount,
        currency=currency,
        reference=reference,
        uid=uid,
        meta=meta,
    )
    ledger = db.get(KEY, []) if isinstance(db, dict) else []
    if not isinstance(ledger, list):
        return ["ledger_shape"]
    for existing in ledger:
        if not isinstance(existing, dict):
            continue
        if (
            str(existing.get("source") or "") == event["source"]
            and str(existing.get("reference") or "") == event["reference"]
        ):
            return _conflicting_fields(existing, event)
    return []


def record_in_db(db, *, source, amount, currency, reference, uid=None, meta=None):
    """Idempotently record against a caller's existing atomic DB transaction."""
    event = _build_event(
        source=source,
        amount=amount,
        currency=currency,
        reference=reference,
        uid=uid,
        meta=meta,
    )
    if not isinstance(db, dict):
        raise ValueError("REVENUE_DB_INVALID")

    ledger = db.setdefault(KEY, [])
    if not isinstance(ledger, list):
        return {"status": "conflict", "event": None, "conflicting_fields": ["ledger_shape"]}

    for existing in ledger:
        if not isinstance(existing, dict):
            continue
        if (
            str(existing.get("source") or "") == event["source"]
            and str(existing.get("reference") or "") == event["reference"]
        ):
            conflicts = _conflicting_fields(existing, event)
            if conflicts:
                return {
                    "status": "conflict",
                    "event": existing,
                    "conflicting_fields": conflicts,
                }
            return {"status": "duplicate", "event": existing}

    ledger.append(event)
    return {"status": "recorded", "event": event}


def record(*, source, amount, currency, reference, uid=None, meta=None):
    """Atomically record a revenue event or report a conflicting replay."""
    event = _build_event(
        source=source,
        amount=amount,
        currency=currency,
        reference=reference,
        uid=uid,
        meta=meta,
    )
    return state_manager.atomic_update(
        lambda db: record_in_db(
            db,
            source=event["source"],
            amount=event["amount"],
            currency=event["currency"],
            reference=event["reference"],
            uid=event["uid"],
            meta=event["meta"],
        )
    )


def summary():
    """Summarize reportable revenue and separately expose exclusions."""
    db = state_manager.load_db()
    raw_rows = db.get(KEY, [])
    raw_rows = raw_rows if isinstance(raw_rows, list) else []
    rows = reportable_rows(db)
    reportable_ids = {id(row) for row in rows}
    totals = {}
    for row in rows:
        cur = str(row.get("currency", "UNKNOWN"))
        totals[cur] = totals.get(cur, 0) + float(row.get("amount", 0) or 0)

    excluded_test_rows = [
        row for row in raw_rows
        if isinstance(row, dict) and is_testish(row)
    ]
    excluded_unverified_rows = [
        row for row in raw_rows
        if isinstance(row, dict)
        and not is_testish(row)
        and id(row) not in reportable_ids
    ]

    def _totals(rows_to_sum):
        result = {}
        for row in rows_to_sum:
            cur = str(row.get("currency") or "UNKNOWN")
            raw_amount = row.get("amount", 0)
            if isinstance(raw_amount, bool):
                continue
            try:
                amount = float(raw_amount or 0)
            except (TypeError, ValueError, OverflowError):
                continue
            if math.isfinite(amount):
                result[cur] = result.get(cur, 0) + amount
        return result

    return {
        "events": len(rows),
        "totals": totals,
        "raw_events": len(raw_rows),
        "excluded_test_events": len(excluded_test_rows),
        "excluded_test_totals": _totals(excluded_test_rows),
        "excluded_unverified_events": len(excluded_unverified_rows),
        "excluded_unverified_totals": _totals(excluded_unverified_rows),
    }
