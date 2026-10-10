"""Safe, atomic Credits hold for manual TON withdrawal requests.

This module does not send a transaction. An authorized operator records a
payout reference only after completing the payout out of band.
"""

import math
import re
import time
from datetime import datetime, timezone

import state_manager
from core.authority import is_owner, has_permission

MIN_WITHDRAW = 1.0
_TON_FRIENDLY = re.compile(r"^(?:EQ|UQ|kQ|0Q)[A-Za-z0-9_-]{46}$")
_TON_RAW = re.compile(r"^-?[0-9]:[0-9a-fA-F]{64}$")

_ERRORS = {
    "INVALID_AMOUNT": "❌ כמות לא תקינה (מינימום 1 credit)",
    "INVALID_ADDRESS": "❌ כתובת TON לא תקינה",
    "USER_NOT_FOUND": "❌ משתמש לא נמצא",
    "INSUFFICIENT_CREDITS": "❌ אין מספיק Credits זמינים",
    "REQUEST_NOT_PENDING": "❌ הבקשה לא נמצאה או שכבר טופלה",
    "REF_REQUIRED": "❌ נדרשת אסמכתא לתשלום שכבר בוצע",
    "BAD_ACTION": "❌ פעולה לא מוכרת",
}


def valid_ton_address(address):
    value = str(address or "").strip()
    return bool(_TON_FRIENDLY.fullmatch(value) or _TON_RAW.fullmatch(value))


def _ledger_entry(uid, before, amount, after, reason, meta):
    return {
        "time": datetime.now(timezone.utc).isoformat(),
        "uid": str(uid),
        "before": before,
        "amount": amount,
        "after": after,
        "reason": reason,
        "meta": meta,
    }


def _next_request_id(db, requests):
    """Monotonic ID that also avoids collisions with older persisted requests."""
    try:
        sequence = int(db.get("withdrawal_seq", 0) or 0)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("WITHDRAWAL_SEQUENCE_INVALID")

    for existing_id in requests:
        match = re.fullmatch(r"W-(\d+)", str(existing_id))
        if match:
            sequence = max(sequence, int(match.group(1)))
    sequence += 1
    return sequence, f"W-{sequence}"


def create_withdrawal(db, uid, amount, address):
    """Atomically hold Credits and create a pending manual withdrawal request."""
    if (
        isinstance(amount, bool)
        or not isinstance(amount, (int, float))
        or not math.isfinite(amount)
        or amount < MIN_WITHDRAW
    ):
        raise ValueError("INVALID_AMOUNT")
    if not valid_ton_address(address):
        raise ValueError("INVALID_ADDRESS")

    uid = str(uid)
    users = db.get("users")
    user = users.get(uid) if isinstance(users, dict) else None
    if not isinstance(user, dict):
        raise ValueError("USER_NOT_FOUND")

    wallet = user.setdefault("wallet", {})
    if not isinstance(wallet, dict):
        raise ValueError("WALLET_INVALID")
    try:
        before = float(wallet.get("credits", 0))
    except (TypeError, ValueError, OverflowError):
        raise ValueError("BALANCE_INVALID")
    if not math.isfinite(before) or before < 0:
        raise ValueError("BALANCE_INVALID")
    amount = float(amount)
    if before < amount:
        raise ValueError("INSUFFICIENT_CREDITS")

    requests = db.get("withdrawal_requests", {})
    if not isinstance(requests, dict):
        raise ValueError("WITHDRAWAL_STORE_INVALID")
    ledger = db.get("ledger", [])
    if not isinstance(ledger, list):
        raise ValueError("LEDGER_INVALID")

    sequence, req_id = _next_request_id(db, requests)
    after = before - amount
    created_at = time.time()

    # All mutations happen only after validation has completed.
    wallet["credits"] = after
    db["withdrawal_seq"] = sequence
    ledger.append(
        _ledger_entry(
            uid,
            before,
            -amount,
            after,
            "withdraw:hold",
            {
                "idempotency_key": f"withdraw:hold:{req_id}",
                "req_id": req_id,
            },
        )
    )
    requests[req_id] = {
        "uid": uid,
        "amount": amount,
        "address": str(address).strip(),
        "status": "pending",
        "created_at": created_at,
    }
    db["withdrawal_requests"] = requests
    return req_id


def resolve_withdrawal(db, req_id, action, admin_uid, ref=None):
    """Resolve a request once. Approval records manual payment; it sends no funds."""
    requests = db.get("withdrawal_requests", {})
    if not isinstance(requests, dict):
        raise ValueError("WITHDRAWAL_STORE_INVALID")
    req = requests.get(str(req_id))
    if not isinstance(req, dict) or req.get("status") != "pending":
        raise ValueError("REQUEST_NOT_PENDING")

    action = str(action or "").strip().lower()
    if action == "approve":
        payout_ref = str(ref or "").strip()
        if not payout_ref or len(payout_ref) > 256:
            raise ValueError("REF_REQUIRED")
        req.update(
            {
                "status": "paid",
                "paid_ref": payout_ref,
                "resolved_by": str(admin_uid),
                "resolved_at": time.time(),
            }
        )
        return req

    if action == "reject":
        uid = str(req.get("uid") or "")
        users = db.get("users")
        user = users.get(uid) if isinstance(users, dict) else None
        if not isinstance(user, dict):
            raise ValueError("USER_NOT_FOUND")
        wallet = user.setdefault("wallet", {})
        if not isinstance(wallet, dict):
            raise ValueError("WALLET_INVALID")
        try:
            amount = float(req.get("amount"))
            before = float(wallet.get("credits", 0))
        except (TypeError, ValueError, OverflowError):
            raise ValueError("WITHDRAWAL_RECORD_INVALID")
        if not math.isfinite(amount) or amount < MIN_WITHDRAW:
            raise ValueError("WITHDRAWAL_RECORD_INVALID")
        if not math.isfinite(before) or before < 0:
            raise ValueError("BALANCE_INVALID")

        ledger = db.get("ledger", [])
        if not isinstance(ledger, list):
            raise ValueError("LEDGER_INVALID")
        after = before + amount
        ledger.append(
            _ledger_entry(
                uid,
                before,
                amount,
                after,
                "withdraw:refund",
                {
                    "idempotency_key": f"withdraw:refund:{req_id}",
                    "req_id": str(req_id),
                },
            )
        )
        wallet["credits"] = after
        req.update(
            {
                "status": "rejected",
                "resolved_by": str(admin_uid),
                "resolved_at": time.time(),
            }
        )
        return req

    raise ValueError("BAD_ACTION")


def _is_admin(uid):
    return is_owner(uid) or has_permission(uid, "agents.manage")


def register(bot):
    @bot.message_handler(commands=["withdraw"])
    def withdraw_cmd(msg):
        parts = (getattr(msg, "text", None) or "").split()
        if len(parts) != 3:
            bot.reply_to(msg, "שימוש: /withdraw <amount_credits> <ton_wallet_address>")
            return
        try:
            amount = float(parts[1])
        except (TypeError, ValueError, OverflowError):
            bot.reply_to(msg, _ERRORS["INVALID_AMOUNT"])
            return

        uid = str(msg.from_user.id)
        address = parts[2].strip()
        try:
            req_id = state_manager.atomic_update(
                lambda db: create_withdrawal(db, uid, amount, address)
            )
        except ValueError as exc:
            bot.reply_to(msg, _ERRORS.get(str(exc), "❌ הבקשה נכשלה"))
            return
        except Exception as exc:
            print("[WITHDRAW] create failed:", type(exc).__name__)
            bot.reply_to(msg, "❌ הבקשה נכשלה; לא בוצעה משיכה")
            return

        bot.reply_to(
            msg,
            f"✅ בקשת משיכה {req_id} נרשמה. ה-Credits נעולים עד לטיפול ידני. "
            "הבוט לא משדר תשלום on-chain.",
        )

    @bot.message_handler(commands=["approve_withdraw"])
    def approve_withdraw_cmd(msg):
        uid = str(msg.from_user.id)
        if not _is_admin(uid):
            bot.reply_to(msg, "⛔️ Admin only")
            return
        parts = (getattr(msg, "text", None) or "").split(maxsplit=2)
        if len(parts) != 3:
            bot.reply_to(
                msg,
                "שימוש: /approve_withdraw <req_id> <payout_ref>\n"
                "השתמש רק לאחר שהתשלום הידני בוצע; הפקודה אינה משדרת כספים.",
            )
            return
        try:
            state_manager.atomic_update(
                lambda db: resolve_withdrawal(db, parts[1], "approve", uid, parts[2])
            )
        except ValueError as exc:
            bot.reply_to(msg, _ERRORS.get(str(exc), "❌ הבקשה נכשלה"))
            return
        except Exception as exc:
            print("[WITHDRAW] approve failed:", type(exc).__name__)
            bot.reply_to(msg, "❌ העדכון נכשל")
            return
        bot.reply_to(msg, f"✅ בקשה {parts[1]} סומנה כשולמה עם אסמכתא. לא נשלחה עסקה על ידי הבוט.")

    @bot.message_handler(commands=["reject_withdraw"])
    def reject_withdraw_cmd(msg):
        uid = str(msg.from_user.id)
        if not _is_admin(uid):
            bot.reply_to(msg, "⛔️ Admin only")
            return
        parts = (getattr(msg, "text", None) or "").split()
        if len(parts) != 2:
            bot.reply_to(msg, "שימוש: /reject_withdraw <req_id>")
            return
        try:
            state_manager.atomic_update(
                lambda db: resolve_withdrawal(db, parts[1], "reject", uid)
            )
        except ValueError as exc:
            bot.reply_to(msg, _ERRORS.get(str(exc), "❌ הבקשה נכשלה"))
            return
        except Exception as exc:
            print("[WITHDRAW] reject failed:", type(exc).__name__)
            bot.reply_to(msg, "❌ דחיית הבקשה נכשלה")
            return
        bot.reply_to(msg, f"✅ בקשה {parts[1]} נדחתה וה-Credits הוחזרו.")
