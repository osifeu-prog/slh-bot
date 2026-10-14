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


def reportable_rows(db, *, currency=None):
    """Return valid, non-test external revenue rows for display only.

    This is a read-only filter. It never modifies the supplied DB or ledger.
    """
    rows = db.get(KEY, []) if isinstance(db, dict) else []
    if not isinstance(rows, list):
        return []
    wanted_currency = str(currency).strip().upper() if currency is not None else None
    reportable = []
    for row in rows:
        if not isinstance(row, dict) or is_testish(row):
            continue
        row_currency = str(row.get("currency") or "").strip()
        if not row_currency:
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
    """Summarize reportable revenue and separately expose excluded test rows."""
    db = state_manager.load_db()
    raw_rows = db.get(KEY, [])
    raw_rows = raw_rows if isinstance(raw_rows, list) else []
    rows = reportable_rows(db)
    totals = {}
    for row in rows:
        cur = str(row.get("currency", "UNKNOWN"))
        totals[cur] = totals.get(cur, 0) + float(row.get("amount", 0) or 0)

    excluded_test_rows = [
        row for row in raw_rows
        if isinstance(row, dict) and is_testish(row)
    ]
    excluded_test_totals = {}
    for row in excluded_test_rows:
        cur = str(row.get("currency") or "UNKNOWN")
        try:
            amount = float(row.get("amount", 0) or 0)
        except (TypeError, ValueError, OverflowError):
            continue
        if math.isfinite(amount):
            excluded_test_totals[cur] = excluded_test_totals.get(cur, 0) + amount

    return {
        "events": len(rows),
        "totals": totals,
        "raw_events": len(raw_rows),
        "excluded_test_events": len(excluded_test_rows),
        "excluded_test_totals": excluded_test_totals,
    }
