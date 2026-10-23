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


def summary(db=None):
    """Summarize revenue from a supplied canonical DB snapshot or load one."""
    db = state_manager.load_db() if db is None else db
    if not isinstance(db, dict):
        raise ValueError("REVENUE_DB_INVALID")
    rows = db.get(KEY, [])
    totals = {}
    for row in rows if isinstance(rows, list) else []:
        cur = str(row.get("currency", "UNKNOWN"))
        totals[cur] = totals.get(cur, 0) + float(row.get("amount", 0) or 0)
    return {"events": len(rows) if isinstance(rows, list) else 0, "totals": totals}
