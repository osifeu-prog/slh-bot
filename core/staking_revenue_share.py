"""Revenue Share distribution engine.

Distributes 80% of net revenue pro-rata to active stake positions.
Never guarantees a fixed yield. If net revenue is 0, distribution is 0.

2026-09-24: reads the canonical `stake_positions` store written by
core/staking_service.py (fields: uid, amount, created_at, unlocks_at,
status="locked"). The previous version read a `staking_positions` key that
no module ever wrote, so every distribution returned no_eligible_stakers.
Positions are per position_id; payouts are aggregated per uid.
"""
from decimal import Decimal
from datetime import datetime, timezone
import state_manager

DISTRIBUTION_RATIO = Decimal("0.80")
ANNUAL_CAP_RATIO = Decimal("0.65")
LOCK_PERIOD_DAYS = 365          # policy constant (not enforced by eligibility)
MIN_STAKE = Decimal("100")      # policy constant (not enforced by eligibility)

POOL_KEY = "revenue_share_pool"
POSITIONS_KEY = "stake_positions"          # canonical, written by staking_service
DISTRIBUTIONS_KEY = "revenue_distributions"


def _now():
    return datetime.now(timezone.utc)


def _dec(value):
    return Decimal(str(value or 0)).quantize(Decimal("0.00000001"))


def _net(gross, costs):
    return max(_dec(gross) - _dec(costs), Decimal("0"))


def _ts(value):
    """stake_positions stores epoch seconds; accept ISO strings too."""
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    dt = datetime.fromisoformat(str(value))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _cap(principal, staked_at):
    days = max((_now() - staked_at).days, 0)
    years = Decimal(days) / Decimal("365")
    return _dec(principal) * ANNUAL_CAP_RATIO * years


def _eligible(db):
    """Active (still locked) positions, keyed by position_id."""
    now = _now()
    out = {}
    for pid, pos in db.get(POSITIONS_KEY, {}).items():
        if pos.get("status") != "locked":
            continue
        try:
            if _ts(pos["unlocks_at"]) <= now:
                continue
            if _dec(pos.get("amount")) <= 0 or not pos.get("uid"):
                continue
        except (KeyError, ValueError, TypeError):
            continue
        out[pid] = pos
    return out


def distribute_revenue(gross_revenue, operating_costs, period_label):
    def mutate(db):
        dists = db.setdefault(DISTRIBUTIONS_KEY, {})
        if period_label in dists:
            return {"status": "duplicate", "period": period_label}

        net = _net(gross_revenue, operating_costs)
        if net <= 0:
            return {"status": "no_revenue", "period": period_label}

        total_to_dist = net * DISTRIBUTION_RATIO
        elig = _eligible(db)
        if not elig:
            return {"status": "no_eligible_stakers", "period": period_label}

        total_staked = sum((_dec(p["amount"]) for p in elig.values()), Decimal("0"))
        if total_staked <= 0:
            return {"status": "no_stake", "period": period_label}

        actual = Decimal("0")
        per_staker = {}
        for pid, pos in elig.items():
            principal = _dec(pos["amount"])
            share = (principal / total_staked) * total_to_dist
            cap = _cap(principal, _ts(pos.get("created_at")))
            already = _dec(pos.get("total_received", 0))
            remaining = max(cap - already, Decimal("0"))
            payout = min(share, remaining)
            if payout <= 0:
                continue
            uid = str(pos["uid"])
            per_staker[uid] = per_staker.get(uid, Decimal("0")) + payout
            actual += payout
            pos["total_received"] = float(already + payout)

        surplus = total_to_dist - actual

        dists[period_label] = {
            "period": period_label,
            "gross_revenue": float(_dec(gross_revenue)),
            "operating_costs": float(_dec(operating_costs)),
            "net_revenue": float(net),
            "total_distributed": float(actual),
            "surplus_to_pool": float(surplus),
            "staker_count": len(per_staker),
            "position_count": len(elig),
            "distributed_at": _now().isoformat(),
        }

        users = db.setdefault("users", {})
        for uid, payout in per_staker.items():
            user = users.get(uid)
            if not user:
                continue
            wallet = user.setdefault("wallet", {})
            current = _dec(wallet.get("revenue_share_claimable", 0))
            wallet["revenue_share_claimable"] = float(current + payout)

        pool = db.setdefault(POOL_KEY, {})
        pool["last_distribution"] = period_label
        pool["total_distributed"] = float(_dec(pool.get("total_distributed", 0)) + actual)
        pool["surplus_accumulated"] = float(_dec(pool.get("surplus_accumulated", 0)) + surplus)

        return {
            "status": "distributed",
            "period": period_label,
            "net_revenue": float(net),
            "total_distributed": float(actual),
            "surplus_to_pool": float(surplus),
            "staker_count": len(per_staker),
        }

    return state_manager.atomic_update(mutate)
