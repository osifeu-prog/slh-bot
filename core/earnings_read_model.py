"""Read-only earnings view for SLH users and Control Plane owners."""

from __future__ import annotations

from typing import Any

import state_manager


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _user(uid: str, db: dict) -> dict:
    user = db.get("users", {}).get(str(uid))
    if not isinstance(user, dict):
        raise ValueError("USER_NOT_FOUND")
    return user


def _staking_pending(uid: str, db: dict) -> float:
    positions = db.get("stake_positions", {})
    pools = db.get("reward_pools", {})
    if not isinstance(positions, dict) or not isinstance(pools, dict):
        return 0.0
    total = 0.0
    for position_id, position in positions.items():
        if not isinstance(position, dict) or str(position.get("uid")) != str(uid):
            continue
        pool = pools.get(str(position_id))
        if not isinstance(pool, dict) or pool.get("status") != "pending":
            continue
        total += max(0.0, _number(pool.get("reward")))
    return round(total, 6)


def get_earnings(uid: str) -> dict:
    uid = str(uid)
    db = state_manager.load_db()
    user = _user(uid, db)
    wallet = user.get("wallet", {}) if isinstance(user.get("wallet"), dict) else {}
    referral = user.get("referral", {}) if isinstance(user.get("referral"), dict) else {}
    distributions = db.get("revenue_distributions", {})
    distributions = distributions if isinstance(distributions, dict) else {}
    revenue_pool = db.get("revenue_share_pool", {})
    revenue_pool = revenue_pool if isinstance(revenue_pool, dict) else {}

    try:
        from core import revenue_ledger
        global_revenue = revenue_ledger.summary()
    except Exception:
        global_revenue = {"events": 0, "totals": {}}

    try:
        from core import staking_revenue_share
        revenue_share_configured = {
            "distribution_ratio": str(staking_revenue_share.DISTRIBUTION_RATIO),
            "min_stake": str(staking_revenue_share.MIN_STAKE),
            "lock_period_days": staking_revenue_share.LOCK_PERIOD_DAYS,
            "distribution_api": "admin_gated",
        }
    except Exception:
        revenue_share_configured = {"distribution_api": "unavailable"}

    claimable = _number(wallet.get("revenue_share_claimable"))
    staking_pending = _staking_pending(uid, db)
    result = {
        "user_id": uid,
        "balances": {
            "credits": _number(wallet.get("credits")),
            "staked": _number(wallet.get("staked")),
            "slh": _number(wallet.get("token_balance")),
        },
        "earnings": {
            "revenue_share_claimable_credits": claimable,
            "staking_reward_pending_credits": staking_pending,
            "referral_commission": _number(wallet.get("referral_commission", referral.get("commission"))),
            "points": int(_number((user.get("gamification") or {}).get("points"))),
        },
        "cash": {
            "status": "telegram_stars_withdrawal_external",
            "status_detail": "SLH records confirmed external revenue; bot-owner withdrawal is handled through Telegram/Fragment rather than the user wallet.",
        },
        "revenue_share": {
            "status": "active_data_requires_distribution",
            "distribution_count": len(distributions),
            "last_distribution": revenue_pool.get("last_distribution"),
            "total_distributed": _number(revenue_pool.get("total_distributed")),
            "surplus_accumulated": _number(revenue_pool.get("surplus_accumulated")),
            "user_claimable_credits": claimable,
            **revenue_share_configured,
        },
        "staking": {
            "pending_reward_credits": staking_pending,
            "reward_claim_path": "existing reward engine",
        },
        "sources": {
            "external_revenue_ledger": "state/db.json:revenue_ledger",
            "user_wallet": "state/db.json:users",
            "staking_rewards": "state/db.json:reward_pools",
        },
        "read_only": True,
    }
    if str(user.get("role", "")).upper() == "OWNER":
        result["system_revenue"] = {
            "confirmed_external_revenue_events": int(global_revenue.get("events", 0) or 0),
            "confirmed_external_revenue_totals": dict(global_revenue.get("totals", {}) or {}),
            "interpretation": "gross recorded external payments; not net cash payout",
        }
    return result
