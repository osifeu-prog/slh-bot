"""SLH Alpha token distribution authority.

All Alpha distributions are transfers from an authorized distributor's
existing SLH balance. This module never mints tokens.
"""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import state_manager
from core.authority import has_permission

LEDGER_KEY = "slh_distribution_ledger"
DISTRIBUTOR_PERMISSION = "alpha.distribute"


def _amount(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("INVALID_AMOUNT")
    if not amount.is_finite() or amount <= 0:
        raise ValueError("INVALID_AMOUNT")
    return amount


def distribute(*, distributor_uid, recipient_uid, amount, reason="alpha_air", event_id=None):
    distributor_uid = str(distributor_uid)
    recipient_uid = str(recipient_uid)
    amount = _amount(amount)
    event_id = str(event_id or "").strip()
    if not event_id:
        raise ValueError("EVENT_ID_REQUIRED")
    if distributor_uid == recipient_uid:
        raise ValueError("SELF_DISTRIBUTION")
    if not has_permission(distributor_uid, DISTRIBUTOR_PERMISSION):
        raise PermissionError("DISTRIBUTOR_NOT_AUTHORIZED")

    def mutate(db):
        users = db.setdefault("users", {})
        sender = users.get(distributor_uid)
        recipient = users.get(recipient_uid)
        if not sender:
            raise ValueError("DISTRIBUTOR_NOT_FOUND")
        if not recipient:
            raise ValueError("RECIPIENT_NOT_FOUND")

        ledger = db.setdefault(LEDGER_KEY, [])
        for entry in ledger:
            if str(entry.get("event_id")) == event_id:
                if (str(entry.get("from_uid")) != distributor_uid or
                        str(entry.get("to_uid")) != recipient_uid or
                        Decimal(str(entry.get("amount", 0))) != amount):
                    raise ValueError("EVENT_ID_CONFLICT")
                return {"status": "already_completed", **entry}

        sender_wallet = sender.setdefault("wallet", {})
        recipient_wallet = recipient.setdefault("wallet", {})
        sender_balance = Decimal(str(sender_wallet.get("token_balance", 0) or 0))
        recipient_balance = Decimal(str(recipient_wallet.get("token_balance", 0) or 0))

        if sender_balance < amount:
            raise ValueError("INSUFFICIENT_S​​LH")

        sender_after = sender_balance - amount
        recipient_after = recipient_balance + amount
        now = datetime.now(timezone.utc).isoformat()
        entry = {
            "event_id": event_id,
            "from_uid": distributor_uid,
            "to_uid": recipient_uid,
            "amount": float(amount),
            "reason": str(reason),
            "before_from": float(sender_balance),
            "after_from": float(sender_after),
            "before_to": float(recipient_balance),
            "after_to": float(recipient_after),
            "timestamp": now,
        }
        sender_wallet["token_balance"] = float(sender_after)
        recipient_wallet["token_balance"] = float(recipient_after)
        ledger.append(entry)
        return {"status": "completed", **entry}

    return state_manager.atomic_update(mutate)
