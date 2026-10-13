"""Revenue observability without inventing cash revenue.

Only record a revenue event when an external payment has actually been
confirmed. Internal Credit spending is not cash revenue and must not be
counted as such.
"""

from datetime import datetime, timezone
import math
import state_manager

KEY = "revenue_ledger"


def _now():
    return datetime.now(timezone.utc).isoformat()


def classify_event_in_db(db, *, source, amount, currency, reference, uid=None):
    """Classify a revenue event against the canonical ledger without mutation.

    A matching (source, reference) is only a duplicate when the immutable
    amount, currency, and UID also match. A malformed ledger fails closed.
    """
    try:
        amount_value = float(amount)
    except (TypeError, ValueError, OverflowError):
        return {"status": "conflict", "event": None, "conflicting_fields": ["amount"]}
    if not math.isfinite(amount_value):
        return {"status": "conflict", "event": None, "conflicting_fields": ["amount"]}

    target_source = str(source)
    target_reference = str(reference)
    target_currency = str(currency)
    target_uid = str(uid) if uid is not None else None
    rows = db.get(KEY, [])
    if not isinstance(rows, list):
        return {
            "status": "conflict",
            "event": None,
            "conflicting_fields": ["ledger_shape"],
        }

    for existing in rows:
        if not isinstance(existing, dict):
            continue
        if (
            str(existing.get("source") or "") != target_source
            or str(existing.get("reference") or "") != target_reference
        ):
            continue

        conflicts = []
        stored_amount = existing.get("amount")
        try:
            normalized_amount = float(stored_amount)
            amount_matches = (
                not isinstance(stored_amount, bool)
                and math.isfinite(normalized_amount)
                and normalized_amount == amount_value
            )
        except (TypeError, ValueError, OverflowError):
            amount_matches = False
        if not amount_matches:
            conflicts.append("amount")

        if existing.get("currency") is None or str(existing.get("currency")) != target_currency:
            conflicts.append("currency")

        stored_uid = existing.get("uid")
        normalized_uid = str(stored_uid) if stored_uid is not None else None
        if normalized_uid != target_uid:
            conflicts.append("uid")

        return {
            "status": "conflict" if conflicts else "duplicate",
            "event": existing,
            "conflicting_fields": conflicts,
        }

    return {"status": "new", "event": None, "conflicting_fields": []}


def record(*, source, amount, currency, reference, uid=None, meta=None):
    if not source or not currency or not reference:
        raise ValueError("REVENUE_REFERENCE_REQUIRED")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        raise ValueError("INVALID_REVENUE_AMOUNT")
    try:
        amount_value = float(amount)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("INVALID_REVENUE_AMOUNT") from exc
    if not math.isfinite(amount_value) or amount_value <= 0:
        raise ValueError("INVALID_REVENUE_AMOUNT")

    event = {
        "timestamp": _now(),
        "source": str(source),
        "amount": amount_value,
        "currency": str(currency),
        "reference": str(reference),
        "uid": str(uid) if uid is not None else None,
        "meta": dict(meta or {}),
    }

    def mutate(db):
        match = classify_event_in_db(
            db,
            source=event["source"],
            amount=event["amount"],
            currency=event["currency"],
            reference=event["reference"],
            uid=event["uid"],
        )
        if match["status"] in {"duplicate", "conflict"}:
            return {
                "status": match["status"],
                "event": match.get("event"),
                **(
                    {"conflicting_fields": match["conflicting_fields"]}
                    if match["status"] == "conflict"
                    else {}
                ),
            }
        ledger = db.setdefault(KEY, [])
        if not isinstance(ledger, list):
            return {
                "status": "conflict",
                "event": None,
                "conflicting_fields": ["ledger_shape"],
            }
        ledger.append(event)
        return {"status": "recorded", "event": event}

    return state_manager.atomic_update(mutate)


def summary():
    db = state_manager.load_db()
    rows = db.get(KEY, [])
    totals = {}
    for row in rows if isinstance(rows, list) else []:
        cur = str(row.get("currency", "UNKNOWN"))
        totals[cur] = totals.get(cur, 0) + float(row.get("amount", 0) or 0)
    return {"events": len(rows) if isinstance(rows, list) else 0, "totals": totals}
