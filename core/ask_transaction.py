"""Durable logical transaction state for paid ASK requests.

The module deliberately uses the existing file-backed state_manager authority so
ASK retries can recover an answer without invoking the LLM again.
"""
from datetime import datetime, timezone

import state_manager


PROCESSING_LEASE_SECONDS = 120


def _now():
    return datetime.now(timezone.utc).isoformat()


def _parse_time(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


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
        now = _now()
        tx = {
            "uid": str(uid),
            "request_id": str(request_id),
            "status": "PENDING",
            "answer": None,
            "created_at": now,
            "updated_at": now,
        }
        rows[key] = tx
        result["transaction"] = tx
        result["created"] = True

    state_manager.atomic_update(mutate)
    return result


def claim_processing(uid, request_id, lease_seconds=PROCESSING_LEASE_SECONDS):
    """Atomically claim the LLM work so concurrent Telegram retries do not both call the provider."""
    key = f"{uid}:{request_id}"
    result = {"claimed": False, "transaction": None}
    now = datetime.now(timezone.utc)

    def mutate(db):
        rows = db.setdefault("ask_transactions", {})
        tx = rows.get(key)
        if tx is None:
            raise ValueError("ASK_TRANSACTION_NOT_FOUND")

        status = tx.get("status")
        if status in ("COMPLETED", "ANSWER_READY"):
            result["transaction"] = tx
            return

        if status == "PROCESSING":
            started = _parse_time(tx.get("processing_at") or tx.get("updated_at"))
            if started is not None:
                age = (now - started).total_seconds()
                if age < max(1, int(lease_seconds)):
                    result["transaction"] = tx
                    return

        if status not in ("PENDING", "FAILED", "PROCESSING"):
            result["transaction"] = tx
            return

        tx["status"] = "PROCESSING"
        tx["processing_at"] = now.isoformat()
        tx["updated_at"] = now.isoformat()
        tx.pop("error", None)
        result["claimed"] = True
        result["transaction"] = tx

    state_manager.atomic_update(mutate)
    return result


def save_answer(uid, request_id, answer):
    """Persist an LLM answer before settlement so a crash cannot force a re-LLM."""
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
        tx["status"] = "ANSWER_READY"
        tx["answer"] = str(answer)
        tx["updated_at"] = _now()
        result["ok"] = True
        result["transaction"] = tx

    state_manager.atomic_update(mutate)
    return result


def complete(uid, request_id):
    """Mark an already-saved answer as settled/completed."""
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
        if tx.get("status") != "ANSWER_READY":
            raise ValueError("ASK_ANSWER_NOT_READY")
        tx["status"] = "COMPLETED"
        tx["updated_at"] = _now()
        result["ok"] = True
        result["transaction"] = tx

    state_manager.atomic_update(mutate)
    return result


def fail(uid, request_id, reason):
    """Mark a failed request, but preserve ANSWER_READY for settlement recovery."""
    key = f"{uid}:{request_id}"

    def mutate(db):
        rows = db.setdefault("ask_transactions", {})
        tx = rows.get(key)
        if tx is None:
            raise ValueError("ASK_TRANSACTION_NOT_FOUND")
        if tx.get("status") in ("COMPLETED", "ANSWER_READY"):
            return
        tx["status"] = "FAILED"
        tx["error"] = str(reason)
        tx["updated_at"] = _now()

    state_manager.atomic_update(mutate)
