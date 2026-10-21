"""Manual monthly VIP renewal funded by internal Credits.

This is deliberately separate from Telegram Stars auto-renewing subscriptions.
The debit, VIP entitlement and ledger event are committed in one canonical DB update.
"""
from __future__ import annotations

import math
import time

import state_manager
from core.stars_price_authority import VIP_SUBSCRIPTION_PERIOD

VIP_CREDITS_MONTH_PRICE = 150


def purchase_vip_month_with_credits(uid, *, now=None):
    uid = str(uid or "").strip()
    if not uid.isdigit():
        return {"status": "INVALID_USER_ID"}

    now = int(time.time() if now is None else now)

    def mutate(db):
        users = db.get("users")
        if not isinstance(users, dict) or not isinstance(users.get(uid), dict):
            return {"status": "USER_NOT_FOUND"}

        user = users[uid]
        try:
            active_until = int(user.get("vip_access_until", 0) or 0)
        except (TypeError, ValueError, OverflowError):
            return {"status": "STATE_INVALID"}

        if active_until > now:
            wallet_view = user.get("wallet") or {}
            return {
                "status": "ACTIVE",
                "vip_access_until": active_until,
                "credits_balance": wallet_view.get("credits", 0) if isinstance(wallet_view, dict) else None,
            }

        wallet = user.get("wallet")
        if wallet is None:
            wallet = {}
        if not isinstance(wallet, dict):
            return {"status": "STATE_INVALID"}

        raw_balance = wallet.get("credits", 0)
        if isinstance(raw_balance, bool):
            return {"status": "STATE_INVALID"}
        try:
            before = float(raw_balance or 0)
        except (TypeError, ValueError, OverflowError):
            return {"status": "STATE_INVALID"}
        if not math.isfinite(before) or before < 0:
            return {"status": "STATE_INVALID"}
        if before < VIP_CREDITS_MONTH_PRICE:
            return {
                "status": "INSUFFICIENT_CREDITS",
                "credits_balance": before,
                "credits_required": VIP_CREDITS_MONTH_PRICE,
            }

        permissions = user.get("permissions", [])
        if permissions is None:
            permissions = []
        if not isinstance(permissions, list):
            return {"status": "STATE_INVALID"}

        ledger = db.get("ledger")
        if ledger is None:
            ledger = []
        if not isinstance(ledger, list):
            return {"status": "STATE_INVALID"}

        after = before - VIP_CREDITS_MONTH_PRICE
        expires_at = max(now, active_until) + int(VIP_SUBSCRIPTION_PERIOD)
        idempotency_key = f"vipcredits:{uid}:{expires_at}"
        if any(
            isinstance(row, dict)
            and isinstance(row.get("meta"), dict)
            and row["meta"].get("idempotency_key") == idempotency_key
            for row in ledger
        ):
            return {"status": "CONFLICT"}

        wallet["credits"] = after
        user["wallet"] = wallet
        user["vip_access_until"] = expires_at
        user["permissions"] = list(permissions) if "vip_access" in permissions else list(permissions) + ["vip_access"]

        ledger.append({
            "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
            "uid": uid,
            "before": before,
            "amount": -VIP_CREDITS_MONTH_PRICE,
            "after": after,
            "reason": "vip:credits_subscription",
            "meta": {
                "idempotency_key": idempotency_key,
                "period_seconds": int(VIP_SUBSCRIPTION_PERIOD),
                "expires_at": expires_at,
                "auto_renew": False,
            },
        })
        db["ledger"] = ledger
        return {
            "status": "APPLIED",
            "credits_balance": after,
            "credits_charged": VIP_CREDITS_MONTH_PRICE,
            "vip_access_until": expires_at,
            "auto_renew": False,
        }

    return state_manager.atomic_update(mutate)
