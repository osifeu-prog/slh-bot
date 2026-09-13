"""Revenue observability without inventing cash revenue.

Only record a revenue event when an external payment has actually been
confirmed. Internal Credit spending is not cash revenue and must not be
counted as such.
"""

from datetime import datetime, timezone
import state_manager

KEY = "revenue_ledger"


def _now():
    return datetime.now(timezone.utc).isoformat()


def record(*, source, amount, currency, reference, uid=None, meta=None):
    if not source or not currency or not reference:
        raise ValueError("REVENUE_REFERENCE_REQUIRED")
    if not isinstance(amount, (int, float)) or amount <= 0:
        raise ValueError("INVALID_REVENUE_AMOUNT")

    event = {
        "timestamp": _now(),
        "source": str(source),
        "amount": float(amount),
        "currency": str(currency),
        "reference": str(reference),
        "uid": str(uid) if uid is not None else None,
        "meta": dict(meta or {}),
    }

    def mutate(db):
        ledger = db.setdefault(KEY, [])
        for existing in ledger:
            if existing.get("source") == event["source"] and existing.get("reference") == event["reference"]:
                return {"status": "duplicate", "event": existing}
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
