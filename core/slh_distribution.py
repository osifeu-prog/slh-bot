"""Canonical SLH token authority for Alpha, P2P, and exchange settlement.

This module never mints tokens. Every SLH mutation is performed here so wallet
balances, exchange reserves, and the canonical token ledger stay auditable and
replay-safe inside the same atomic state transition.
"""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import state_manager
from core.authority import has_permission

TOKEN_LEDGER_KEY = "slh_token_ledger"
DISTRIBUTOR_PERMISSION = "alpha.distribute"
EXCHANGE_RESERVE_KEY = "exchange_reserved_slh"
EXCHANGE_RESERVE_UID = "__EXCHANGE_RESERVE__"


def _amount(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("INVALID_AMOUNT")
    if not amount.is_finite() or amount <= 0:
        raise ValueError("INVALID_AMOUNT")
    return amount


def _users(db):
    return db.setdefault("users", {})


def _wallet(db, uid):
    user = _users(db).get(str(uid))
    if not user:
        raise ValueError("USER_NOT_FOUND")
    return user.setdefault("wallet", {})


def _find_event(ledger, event_id):
    for entry in ledger:
        if str(entry.get("event_id")) == event_id:
            return entry
    return None


def _transfer_in_db(db, *, from_uid, to_uid, amount, reason, event_id):
    from_uid = str(from_uid)
    to_uid = str(to_uid)
    amount = _amount(amount)
    event_id = str(event_id or "").strip()
    if not event_id:
        raise ValueError("EVENT_ID_REQUIRED")
    if from_uid == to_uid:
        raise ValueError("SELF_TRANSFER")

    users = _users(db)
    sender = users.get(from_uid)
    recipient = users.get(to_uid)
    if not sender:
        raise ValueError("SENDER_NOT_FOUND")
    if not recipient:
        raise ValueError("RECIPIENT_NOT_FOUND")

    ledger = db.setdefault(TOKEN_LEDGER_KEY, [])
    existing = _find_event(ledger, event_id)
    if existing:
        if (
            str(existing.get("from_uid")) != from_uid
            or str(existing.get("to_uid")) != to_uid
            or Decimal(str(existing.get("amount", 0))) != amount
        ):
            raise ValueError("EVENT_ID_CONFLICT")
        return {"status": "already_completed", **existing}

    sender_wallet = sender.setdefault("wallet", {})
    recipient_wallet = recipient.setdefault("wallet", {})
    sender_balance = Decimal(str(sender_wallet.get("token_balance", 0) or 0))
    recipient_balance = Decimal(str(recipient_wallet.get("token_balance", 0) or 0))
    sender_live = Decimal(str(sender_wallet.get("live_token_balance", 0) or 0))
    recipient_live = Decimal(str(recipient_wallet.get("live_token_balance", 0) or 0))
    if sender_live < amount:
        raise ValueError("INSUFFICIENT_LIVE_SLH")

    sender_after = sender_balance - amount
    recipient_after = recipient_balance + amount
    sender_live_after = sender_live - amount
    recipient_live_after = recipient_live + amount
    entry = {
        "event_id": event_id, "from_uid": from_uid, "to_uid": to_uid,
        "amount": float(amount), "reason": str(reason), "kind": "wallet_transfer",
        "before_from": float(sender_balance), "after_from": float(sender_after),
        "before_to": float(recipient_balance), "after_to": float(recipient_after),
        "before_live_from": float(sender_live), "after_live_from": float(sender_live_after),
        "before_live_to": float(recipient_live), "after_live_to": float(recipient_live_after),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    sender_wallet["token_balance"] = float(sender_after)
    recipient_wallet["token_balance"] = float(recipient_after)
    sender_wallet["live_token_balance"] = float(sender_live_after)
    recipient_wallet["live_token_balance"] = float(recipient_live_after)
    ledger.append(entry)
    return {"status": "completed", **entry}


def reserve_in_db(db, *, uid, amount, event_id, order_id=None, reason="exchange:sell_reserve"):
    """Move available SLH into exchange escrow without changing supply."""
    uid = str(uid)
    amount = _amount(amount)
    event_id = str(event_id or "").strip()
    if not event_id:
        raise ValueError("EVENT_ID_REQUIRED")

    ledger = db.setdefault(TOKEN_LEDGER_KEY, [])
    existing = _find_event(ledger, event_id)
    if existing:
        if (str(existing.get("from_uid")) != uid
                or Decimal(str(existing.get("amount", 0))) != amount
                or existing.get("kind") != "exchange_reserve"):
            raise ValueError("EVENT_ID_CONFLICT")
        return {"status": "already_completed", **existing}

    wallet = _wallet(db, uid)
    total_before = Decimal(str(wallet.get("token_balance", 0) or 0))
    available = Decimal(str(wallet.get("live_token_balance", 0) or 0))
    reserve_before = Decimal(str(wallet.get(EXCHANGE_RESERVE_KEY, 0) or 0))
    if available < amount or total_before < amount:
        raise ValueError("INSUFFICIENT_LIVE_SLH")

    total_after = total_before
    available_after = available
    reserve_after = reserve_before + amount
    wallet["token_balance"] = float(total_after)
    wallet["live_token_balance"] = float(available_after)
    wallet[EXCHANGE_RESERVE_KEY] = float(reserve_after)
    entry = {
        "event_id": event_id, "from_uid": uid, "to_uid": EXCHANGE_RESERVE_UID,
        "amount": float(amount), "reason": str(reason), "kind": "exchange_reserve",
        "order_id": order_id, "before_from": float(total_before), "after_from": float(total_after),
        "before_live_from": float(available), "after_live_from": float(available_after),
        "before_reserve": float(reserve_before), "after_reserve": float(reserve_after),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    ledger.append(entry)
    return {"status": "completed", **entry}


def release_reserve_in_db(db, *, uid, amount, event_id, order_id=None, reason="exchange:cancel_release_slh"):
    """Return SLH from exchange escrow to the owner's available wallet."""
    uid = str(uid)
    amount = _amount(amount)
    event_id = str(event_id or "").strip()
    if not event_id:
        raise ValueError("EVENT_ID_REQUIRED")

    ledger = db.setdefault(TOKEN_LEDGER_KEY, [])
    existing = _find_event(ledger, event_id)
    if existing:
        if (str(existing.get("to_uid")) != uid
                or Decimal(str(existing.get("amount", 0))) != amount
                or existing.get("kind") != "exchange_release"):
            raise ValueError("EVENT_ID_CONFLICT")
        return {"status": "already_completed", **existing}

    wallet = _wallet(db, uid)
    reserve_before = Decimal(str(wallet.get(EXCHANGE_RESERVE_KEY, 0) or 0))
    available_before = Decimal(str(wallet.get("token_balance", 0) or 0))
    live_before = Decimal(str(wallet.get("live_token_balance", 0) or 0))
    if reserve_before < amount:
        raise ValueError("INSUFFICIENT_SLH_RESERVE")

    reserve_after = reserve_before - amount
    available_after = available_before
    live_after = live_before
    wallet[EXCHANGE_RESERVE_KEY] = float(reserve_after)
    wallet["token_balance"] = float(available_after)
    wallet["live_token_balance"] = float(live_after)
    entry = {
        "event_id": event_id, "from_uid": EXCHANGE_RESERVE_UID, "to_uid": uid,
        "amount": float(amount), "reason": str(reason), "kind": "exchange_release",
        "order_id": order_id, "before_reserve": float(reserve_before),
        "after_reserve": float(reserve_after), "before_to": float(available_before),
        "after_to": float(available_after), "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    ledger.append(entry)
    return {"status": "completed", **entry}


def settle_reserve_in_db(
    db, *, seller_uid, buyer_uid, amount, event_id, order_id=None,
    trade_id=None, reason="exchange:settlement_slh"
):
    """Settle reserved seller SLH directly into the buyer wallet."""
    seller_uid = str(seller_uid)
    buyer_uid = str(buyer_uid)
    amount = _amount(amount)
    event_id = str(event_id or "").strip()
    if not event_id:
        raise ValueError("EVENT_ID_REQUIRED")
    if seller_uid == buyer_uid:
        raise ValueError("SELF_TRANSFER")

    ledger = db.setdefault(TOKEN_LEDGER_KEY, [])
    existing = _find_event(ledger, event_id)
    if existing:
        if (
            str(existing.get("from_uid")) != EXCHANGE_RESERVE_UID
            or str(existing.get("to_uid")) != buyer_uid
            or str(existing.get("seller_uid")) != seller_uid
            or Decimal(str(existing.get("amount", 0))) != amount
            or existing.get("kind") != "exchange_settlement"
        ):
            raise ValueError("EVENT_ID_CONFLICT")
        return {"status": "already_completed", **existing}

    seller = _wallet(db, seller_uid)
    buyer = _wallet(db, buyer_uid)
    seller_reserve_before = Decimal(str(seller.get(EXCHANGE_RESERVE_KEY, 0) or 0))
    seller_total_before = Decimal(str(seller.get("token_balance", 0) or 0))
    buyer_before = Decimal(str(buyer.get("token_balance", 0) or 0))
    buyer_live_before = Decimal(str(buyer.get("live_token_balance", 0) or 0))
    if seller_reserve_before < amount:
        raise ValueError("INSUFFICIENT_SLH_RESERVE")
    if seller_total_before < amount:
        raise ValueError("SLH_TOTAL_BALANCE_BREACH")

    seller_reserve_after = seller_reserve_before - amount
    seller_total_after = seller_total_before - amount
    seller_live_before = Decimal(str(seller.get("live_token_balance", 0) or 0))
    if seller_live_before < amount:
        raise ValueError("INSUFFICIENT_LIVE_SLH")
    seller_live_after = seller_live_before - amount
    buyer_after = buyer_before + amount
    buyer_live_after = buyer_live_before + amount
    seller[EXCHANGE_RESERVE_KEY] = float(seller_reserve_after)
    seller["token_balance"] = float(seller_total_after)
    seller["live_token_balance"] = float(seller_live_after)
    buyer["token_balance"] = float(buyer_after)
    buyer["live_token_balance"] = float(buyer_live_after)
    entry = {
        "event_id": event_id, "from_uid": EXCHANGE_RESERVE_UID, "to_uid": buyer_uid,
        "seller_uid": seller_uid, "amount": float(amount), "reason": str(reason),
        "kind": "exchange_settlement", "order_id": order_id, "trade_id": trade_id,
        "before_reserve": float(seller_reserve_before), "after_reserve": float(seller_reserve_after),
        "before_from_total": float(seller_total_before), "after_from_total": float(seller_total_after),
        "before_live_from": float(seller_live_before), "after_live_from": float(seller_live_after),
        "before_to": float(buyer_before), "after_to": float(buyer_after),
        "before_live_to": float(buyer_live_before), "after_live_to": float(buyer_live_after),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    ledger.append(entry)
    return {"status": "completed", **entry}


def transfer(*, sender_uid, recipient_uid, amount, event_id, reason="p2p"):
    return state_manager.atomic_update(
        lambda db: _transfer_in_db(
            db, from_uid=sender_uid, to_uid=recipient_uid,
            amount=amount, reason=reason, event_id=event_id,
        )
    )


def distribute(*, distributor_uid, recipient_uid, amount, reason="alpha_air", event_id=None):
    distributor_uid = str(distributor_uid)
    if not has_permission(distributor_uid, DISTRIBUTOR_PERMISSION):
        raise PermissionError("DISTRIBUTOR_NOT_AUTHORIZED")
    return state_manager.atomic_update(
        lambda db: _transfer_in_db(
            db, from_uid=distributor_uid, to_uid=recipient_uid,
            amount=amount, reason=reason, event_id=event_id,
        )
    )
