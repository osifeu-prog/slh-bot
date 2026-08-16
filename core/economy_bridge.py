"""
SLH Economy Bridge

Compatibility facade for legacy economy callers.
All credit mutations are delegated to the Money Authority.
"""

from core import money_service, profile_manager, reward_engine


def get_balance(uid):
    return profile_manager.get_balance(uid)


def add_credits(uid, amount, reason="economy_bridge_add"):
    if amount <= 0:
        raise ValueError("add_credits requires a positive amount")

    return money_service.credit(
        uid,
        amount,
        reason=reason,
        source="economy_bridge",
    )


def spend_credits(uid, amount, reason="economy_bridge_spend"):
    if amount <= 0:
        raise ValueError("spend_credits requires a positive amount")

    return money_service.debit(
        uid,
        amount,
        reason=reason,
        source="economy_bridge",
    )


def reward(uid, credits=0, points=0, reason="economy_reward"):
    return reward_engine.grant(
        uid,
        reason=reason,
        credits=credits,
        points=points,
    )


def spend(uid, amount, reason=None):
    return spend_credits(
        uid,
        amount,
        reason=reason or "economy_bridge_spend",
    )
