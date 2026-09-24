"""One-time correction for SLH sell orders that were cancelled OUTSIDE the
canonical /cancel path (reserve zeroed, SLH never released to the owner).

Evidence rule — a correction is allowed only when ALL are true:
  * order exists, side == "sell", status == "cancelled"
  * order.reserved_slh == 0 and order.remaining_amount == 0
  * a matching "exchange:sell_reserve" ledger entry exists for the order
  * no release was ever recorded (neither slh_token_ledger
    "exchange:release_slh:<oid>" nor ledger "exchange:cancel_release_slh")
  * amount to restore = original_amount - SLH actually filled in trades

The correction is idempotent (event_id "correction:missed_release:<oid>"),
writes one slh_token_ledger entry and one ledger entry, and never touches
any other account. Default is DRY RUN.
"""
from datetime import datetime, timezone
from decimal import Decimal

import state_manager

TOKEN_LEDGER_KEY = "slh_token_ledger"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _plan(db, order_id):
    order = (db.get("exchange_orders") or {}).get(order_id)
    if not order:
        raise ValueError("ORDER_NOT_FOUND")
    if order.get("side") != "sell" or order.get("status") != "cancelled":
        raise ValueError("NOT_A_CANCELLED_SELL_ORDER")
    if Decimal(str(order.get("reserved_slh", "0"))) != 0 or Decimal(str(order.get("remaining_amount", "0"))) != 0:
        raise ValueError("ORDER_STILL_HOLDS_RESERVE")

    uid = str(order["uid"])
    ledger = db.get("ledger", [])
    token_ledger = db.get(TOKEN_LEDGER_KEY, [])

    reserved = [e for e in ledger
                if e.get("reason") == "exchange:sell_reserve"
                and (e.get("meta") or {}).get("order_id") == order_id
                and str(e.get("uid")) == uid]
    if not reserved:
        raise ValueError("NO_RESERVE_EVIDENCE")

    released = any(str(e.get("event_id")) == f"exchange:release_slh:{order_id}" for e in token_ledger) or any(
        e.get("reason") == "exchange:cancel_release_slh" and (e.get("meta") or {}).get("order_id") == order_id
        for e in ledger)
    if released:
        raise ValueError("RELEASE_ALREADY_RECORDED")

    filled = sum((Decimal(str(t.get("slh_amount", "0"))) for t in db.get("exchange_trades", [])
                  if t.get("sell_order_id") == order_id), Decimal("0"))
    missing = Decimal(str(order["original_amount"])) - filled
    if missing <= 0:
        raise ValueError("NOTHING_TO_RESTORE")

    wallet = ((db.get("users") or {}).get(uid) or {}).get("wallet")
    if wallet is None:
        raise ValueError("USER_NOT_FOUND")
    before = Decimal(str(wallet.get("token_balance", 0) or 0))
    return {"order_id": order_id, "uid": uid, "original": str(order["original_amount"]),
            "filled": str(filled), "restore": str(missing),
            "token_balance_before": str(before), "token_balance_after": str(before + missing)}


def correct_missed_release(order_id, operator_uid, apply=False, note=""):
    event_id = f"correction:missed_release:{order_id}"

    if not apply:
        db = state_manager.load_db()
        if any(str(e.get("event_id")) == event_id for e in db.get(TOKEN_LEDGER_KEY, [])):
            return {"status": "already_corrected", "order_id": order_id}
        return {"status": "dry_run", **_plan(db, order_id)}

    def mutate(db):
        token_ledger = db.setdefault(TOKEN_LEDGER_KEY, [])
        if any(str(e.get("event_id")) == event_id for e in token_ledger):
            return {"status": "already_corrected", "order_id": order_id}
        plan = _plan(db, order_id)
        uid, amount = plan["uid"], Decimal(plan["restore"])
        wallet = db["users"][uid].setdefault("wallet", {})
        before = Decimal(str(wallet.get("token_balance", 0) or 0))
        after = before + amount
        now = _now()
        wallet["token_balance"] = float(after)
        token_ledger.append({
            "event_id": event_id, "kind": "reserve_release_correction",
            "reason": "exchange:missed_release_correction",
            "from_uid": "__EXCHANGE_RESERVE__", "to_uid": uid, "amount": float(amount),
            "before_to": float(before), "after_to": float(after),
            "order_id": order_id, "operator_uid": str(operator_uid), "note": note, "timestamp": now,
        })
        db.setdefault("ledger", []).append({
            "time": now, "uid": uid, "before": float(before), "amount": float(amount), "after": float(after),
            "reason": "exchange:missed_release_correction",
            "meta": {"order_id": order_id, "event_id": event_id, "asset": "SLH", "operator_uid": str(operator_uid), "note": note},
        })
        return {"status": "corrected", **plan}

    return state_manager.atomic_update(mutate)
