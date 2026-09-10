"""Canonical SLH token authority for Alpha distribution and P2P transfers.

This module never mints tokens. Every mutation transfers existing SLH from
one wallet to another inside a single atomic state transition and records a
replay-safe token ledger entry.
"""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import state_manager
from core.authority import has_permission

TOKEN_LEDGER_KEY = "slh_token_ledger"
DISTRIBUTOR_PERMISSION = "alpha.distribute"


def _amount(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("INVALID_AMOUNT")
    if not amount.is_finite() or amount <= 0:
        raise ValueError("INVALID_AMOUNT")
    return amount


def _transfer_in_db(db, *, from_uid, to_uid, amount, reason, event_id):
    from_uid = str(from_uid)
    to_uid = str(to_uid)
    amount = _amount(amount)
    event_id = str(event_id or "").strip()
    if not event_id:
        raise ValueError("EVENT_ID_REQUIRED")
    if from_uid == to_uid:
        raise ValueError("SELF_TRANSFER")

    users = db.setdefault("users", {})
    sender = users.get(from_uid)
    recipient = users.get(to_uid)
    if not sender:
        raise ValueError("SENDER_NOT_FOUND")
    if not recipient:
        raise ValueError("RECIPIENT_NOT_FOUND")

    ledger = db.setdefault(TOKEN_LEDGER_KEY, [])
    for entry in ledger:
        if str(entry.get("event_id")) == event_id:
            if (
                str(entry.get("from_uid")) != from_uid
                or str(entry.get("to_uid")) != to_uid
                or Decimal(str(entry.get("amount", 0))) != amount
            ):
                raise ValueError("EVENT_ID_CONFLICT")
            return {"status": "already_completed", **entry}

    sender_wallet = sender.setdefault("wallet", {})
    recipient_wallet = recipient.setdefault("wallet", {})
    sender_balance = Decimal(str(sender_wallet.get("token_balance", 0) or 0))
    recipient_balance = Decimal(str(recipient_wallet.get("token_balance", 0) or 0))

    if sender_balance < amount:
        raise ValueError("INSUFFICIENT_SLH")

    sender_after = sender_balance - amount
    recipient_after = recipient_balance + amount
    entry = {
        "event_id": event_id,
        "from_uid": from_uid,
        "to_uid": to_uid,
        "amount": float(amount),
        "reason": str(reason),
        "before_from": float(sender_balance),
        "after_from": float(sender_after),
        "before_to": float(recipient_balance),
        "after_to": float(recipient_after),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    sender_wallet["token_balance"] = float(sender_after)
    recipient_wallet["token_balance"] = float(recipient_after)
    ledger.append(entry)
    return {"status": "completed", **entry}


def transfer(*, sender_uid, recipient_uid, amount, event_id, reason="p2p"):
    return state_manager.atomic_update(
        lambda db: _transfer_in_db(
            db,
            from_uid=sender_uid,
            to_uid=recipient_uid,
            amount=amount,
            reason=reason,
            event_id=event_id,
        )
    )


def distribute(*, distributor_uid, recipient_uid, amount, reason="alpha_air", event_id=None):
    distributor_uid = str(distributor_uid)
    if not has_permission(distributor_uid, DISTRIBUTOR_PERMISSION):
        raise PermissionError("DISTRIBUTOR_NOT_AUTHORIZED")
    return state_manager.atomic_update(
        lambda db: _transfer_in_db(
            db,
            from_uid=distributor_uid,
            to_uid=recipient_uid,
            amount=amount,
            reason=reason,
            event_id=event_id,
        )
    )
