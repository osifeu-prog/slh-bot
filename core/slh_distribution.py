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



def _append_exchange_audit(db, *, uid, before, amount, reason, meta):
    """Record an exchange balance mutation without treating a reserve as supply."""
    before = Decimal(str(before))
    amount = Decimal(str(amount))
    db.setdefault("ledger", []).append({
        "time": datetime.now(timezone.utc).isoformat(),
        "uid": str(uid),
        "before": float(before),
        "amount": float(amount),
        "after": float(before + amount),
        "reason": str(reason),
        "meta": meta,
    })


def _reserve_in_db(db, *, uid, amount, order_id):
    """Move existing SLH from available balance into an exchange reserve."""
    uid = str(uid)
    amount = _amount(amount)
    user = db.setdefault("users", {}).get(uid)
    if not user:
        raise ValueError("SENDER_NOT_FOUND")
    wallet = user.setdefault("wallet", {})
    balance = Decimal(str(wallet.get("token_balance", 0) or 0))
    reserve = Decimal(str(wallet.get("exchange_reserved_slh", 0) or 0))
    if balance < amount:
        raise ValueError("INSUFFICIENT_SLH")
    wallet["token_balance"] = float(balance - amount)
    wallet["exchange_reserved_slh"] = float(reserve + amount)
    _append_exchange_audit(
        db, uid=uid, before=balance, amount=-amount,
        reason="exchange:sell_reserve", meta={"order_id": str(order_id)}
    )
    return {"status": "completed", "uid": uid, "amount": float(amount)}


def _release_reserved_in_db(db, *, uid, amount, order_id):
    """Release reserved SLH back to the owner's available balance."""
    uid = str(uid)
    amount = _amount(amount)
    user = db.setdefault("users", {}).get(uid)
    if not user:
        raise ValueError("USER_NOT_FOUND")
    wallet = user.setdefault("wallet", {})
    reserve = Decimal(str(wallet.get("exchange_reserved_slh", 0) or 0))
    balance = Decimal(str(wallet.get("token_balance", 0) or 0))
    if reserve < amount:
        raise ValueError("INSUFFICIENT_RESERVED_SLH")
    wallet["exchange_reserved_slh"] = float(reserve - amount)
    wallet["token_balance"] = float(balance + amount)
    _append_exchange_audit(
        db, uid=uid, before=balance, amount=amount,
        reason="exchange:cancel_release_slh", meta={"order_id": str(order_id)}
    )
    return {"status": "completed", "uid": uid, "amount": float(amount)}


def _settle_reserved_in_db(
    db, *, seller_uid, buyer_uid, amount, event_id, trade_id, sell_order_id, buy_order_id
):
    """Transfer reserved SLH from seller to buyer as one canonical ownership change."""
    seller_uid = str(seller_uid)
    buyer_uid = str(buyer_uid)
    amount = _amount(amount)
    event_id = str(event_id or "").strip()
    if not event_id:
        raise ValueError("EVENT_ID_REQUIRED")
    if seller_uid == buyer_uid:
        raise ValueError("SELF_TRANSFER")

    users = db.setdefault("users", {})
    seller = users.get(seller_uid)
    buyer = users.get(buyer_uid)
    if not seller:
        raise ValueError("SENDER_NOT_FOUND")
    if not buyer:
        raise ValueError("RECIPIENT_NOT_FOUND")

    ledger = db.setdefault(TOKEN_LEDGER_KEY, [])
    for entry in ledger:
        if str(entry.get("event_id")) == event_id:
            if (
                str(entry.get("from_uid")) != seller_uid
                or str(entry.get("to_uid")) != buyer_uid
                or Decimal(str(entry.get("amount", 0))) != amount
            ):
                raise ValueError("EVENT_ID_CONFLICT")
            return {"status": "already_completed", **entry}

    seller_wallet = seller.setdefault("wallet", {})
    buyer_wallet = buyer.setdefault("wallet", {})
    seller_reserve = Decimal(str(seller_wallet.get("exchange_reserved_slh", 0) or 0))
    buyer_balance = Decimal(str(buyer_wallet.get("token_balance", 0) or 0))
    if seller_reserve < amount:
        raise ValueError("INSUFFICIENT_RESERVED_SLH")

    seller_wallet["exchange_reserved_slh"] = float(seller_reserve - amount)
    buyer_wallet["token_balance"] = float(buyer_balance + amount)

    entry = {
        "event_id": event_id,
        "from_uid": seller_uid,
        "to_uid": buyer_uid,
        "amount": float(amount),
        "reason": "exchange:settlement_slh",
        "before_from_reserve": float(seller_reserve),
        "after_from_reserve": float(seller_reserve - amount),
        "before_to": float(buyer_balance),
        "after_to": float(buyer_balance + amount),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "meta": {
            "trade_id": str(trade_id),
            "sell_order_id": str(sell_order_id),
            "buy_order_id": str(buy_order_id),
        },
    }
    ledger.append(entry)
    return {"status": "completed", **entry}


def reserve(*, uid, amount, order_id):
    return state_manager.atomic_update(
        lambda db: _reserve_in_db(db, uid=uid, amount=amount, order_id=order_id)
    )


def release_reserved(*, uid, amount, order_id):
    return state_manager.atomic_update(
        lambda db: _release_reserved_in_db(db, uid=uid, amount=amount, order_id=order_id)
    )


def settle_reserved(
    *, seller_uid, buyer_uid, amount, event_id, trade_id, sell_order_id, buy_order_id
):
    return state_manager.atomic_update(
        lambda db: _settle_reserved_in_db(
            db,
            seller_uid=seller_uid,
            buyer_uid=buyer_uid,
            amount=amount,
            event_id=event_id,
            trade_id=trade_id,
            sell_order_id=sell_order_id,
            buy_order_id=buy_order_id,
        )
    )

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
