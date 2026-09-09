"""Durable logical transaction state for paid ASK requests.

The module deliberately uses the existing file-backed state_manager authority so
ASK retries can recover a completed answer without invoking the LLM again.
"""
from datetime import datetime, timezone

import state_manager


def _now():
    return datetime.now(timezone.utc).isoformat()


def get_transaction(uid, request_id):
    if not uid or not request_id:
        return None
    db = state_manager.load_db()
    rows = db.get("ask_transactions", {})
    return rows.get(f"{uid}:{request_id}")


def begin_or_get(uid, request_id):
    """Atomically create PENDING state or return an existing transaction."""
    if not uid or not request_id:
        return None
    key = f"{uid}:{request_id}"
    result = {"transaction": None, "created": False}

    def mutate(db):
        rows = db.setdefault("ask_transactions", {})
        existing = rows.get(key)
        if existing is not None:
            result["transaction"] = existing
            return
        tx = {
            "uid": str(uid),
            "request_id": str(request_id),
            "status": "PENDING",
            "answer": None,
            "created_at": _now(),
            "updated_at": _now(),
        }
        rows[key] = tx
        result["transaction"] = tx
        result["created"] = True

    state_manager.atomic_update(mutate)
    return result


def complete(uid, request_id, answer):
    """Persist the successful answer atomically with transaction state."""
    key = f"{uid}:{request_id}"
    result = {"ok": False, "transaction": None}

    def mutate(db):
        rows = db.setdefault("ask_transactions", {})
        tx = rows.get(key)
        if tx is None:
            raise ValueError("ASK_TRANSACTION_NOT_FOUND")
        if tx.get("status") == "COMPLETED":
            result["ok"] = True
            result["transaction"] = tx
            return
        tx["status"] = "COMPLETED"
        tx["answer"] = answer
        tx["updated_at"] = _now()
        result["ok"] = True
        result["transaction"] = tx

    state_manager.atomic_update(mutate)
    return result


def fail(uid, request_id, reason):
    """Mark a failed request so it can be retried deliberately."""
    key = f"{uid}:{request_id}"

    def mutate(db):
        rows = db.setdefault("ask_transactions", {})
        tx = rows.get(key)
        if tx is None:
            raise ValueError("ASK_TRANSACTION_NOT_FOUND")
        if tx.get("status") != "COMPLETED":
            tx["status"] = "FAILED"
            tx["error"] = str(reason)
            tx["updated_at"] = _now()

    state_manager.atomic_update(mutate)
