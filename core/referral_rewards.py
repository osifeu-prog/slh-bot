"""Referral milestone rewards.

Milestones are funded in internal Credits only. No token minting or SLH
distribution is performed here. Every milestone is idempotent per referrer.
"""

from core.reward_engine import grant

MILESTONES = {
    5: {"credits": 500, "reason": "referral_milestone_5"},
}


def settle(uid, referral_count):
    """Grant newly reached referral milestones exactly once."""
    uid = str(uid)
    count = int(referral_count or 0)
    results = []

    for threshold, reward in sorted(MILESTONES.items()):
        if count < threshold:
            continue
        key = f"referral-milestone:{threshold}:{uid}"
        results.append({
            "threshold": threshold,
            "reward": dict(reward),
            "result": grant(
                uid,
                reward["reason"],
                credits=int(reward["credits"]),
                idempotency_key=key,
            ),
        })

    return results
