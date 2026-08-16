from core import profile_manager
from core import economy_service


def get_balance(uid):
    return economy_service.get_balance_safe(uid)


def add_credits(uid, amount, reason="bridge:add_credits", meta=None):
    """
    Single credit mutation gateway.

    IMPORTANT:
    All credit mutations are delegated to economy_service.record_transaction().
    This keeps db.json and state/ledger.json synchronized.
    """
    return economy_service.record_transaction(
        uid=uid,
        amount=amount,
        reason=reason,
        meta=meta or {}
    )


def spend_credits(uid, amount, reason="bridge:spend_credits", meta=None):
    """
    Spend credits through the transaction authority.

    Preserves the previous insufficient-balance behavior:
    returns False instead of allowing a negative balance.
    """
    if amount < 0:
        raise ValueError("spend amount must be >= 0")

    current = economy_service.get_balance_safe(uid)

    if current < amount:
        return False

    return economy_service.record_transaction(
        uid=uid,
        amount=-amount,
        reason=reason,
        meta=meta or {}
    )


def add_points(uid, amount):
    """
    Points are intentionally kept outside the credit transaction authority.
    """
    return profile_manager.add_points(uid, amount)


def reward(uid, credits=0, points=0, reason="bridge:reward", meta=None):
    """
    Unified reward gateway.

    Credits -> Transaction Authority
    Points  -> existing profile manager
    """
    result = {}
    meta = meta or {}

    if credits:
        result["credits"] = add_credits(
            uid,
            credits,
            reason=reason,
            meta=meta
        )

    if points:
        result["points"] = add_points(
            uid,
            points
        )

    return result


def spend(uid, amount, reason=None, meta=None):
    """
    Compatibility alias used by store/engine.py.
    """
    return spend_credits(
        uid,
        amount,
        reason=reason or "bridge:spend",
        meta=meta
    )
