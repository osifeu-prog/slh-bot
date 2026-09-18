"""Revenue Share distribution engine.

Distributes 80% of net ESP revenue pro-rata to stakers.
Never guarantees a fixed yield. If net revenue is 0, distribution is 0.
"""
from decimal import Decimal
from datetime import datetime, timezone, timedelta
import state_manager

DISTRIBUTION_RATIO = Decimal("0.80")
ANNUAL_CAP_RATIO = Decimal("0.65")
LOCK_PERIOD_DAYS = 365
MIN_STAKE = Decimal("100")

POOL_KEY = "revenue_share_pool"
POSITIONS_KEY = "staking_positions"
DISTRIBUTIONS_KEY = "revenue_distributions"


def _now():
    return datetime.now(timezone.utc)


def _dec(value):
    return Decimal(str(value or 0)).quantize(Decimal("0.00000001"))


def _net(gross, costs):
    return max(_dec(gross) - _dec(costs), Decimal("0"))


def _cap(principal, staked_at):
    days = (_now() - staked_at).days
    years = Decimal(days) / Decimal("365")
    return _dec(principal) * ANNUAL_CAP_RATIO * years


def _eligible(db):
    now = _now()
    out = {}
    for uid, pos in db.get(POSITIONS_KEY, {}).items():
        if pos.get("status") != "active":
            continue
        if datetime.fromisoformat(pos["unlock_at"]) <= now:
            continue
        out[uid] = pos
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

        total_staked = sum((_dec(p["principal"]) for p in elig.values()), Decimal("0"))
        if total_staked <= 0:
            return {"status": "no_stake", "period": period_label}

        actual = Decimal("0")
        per_staker = {}
        for uid, pos in elig.items():
            principal = _dec(pos["principal"])
            share = (principal / total_staked) * total_to_dist
            staked_at = datetime.fromisoformat(pos["staked_at"])
            cap = _cap(principal, staked_at)
            already = _dec(pos.get("total_received", 0))
            remaining = max(cap - already, Decimal("0"))
            payout = min(share, remaining)
            if payout <= 0:
                continue
            per_staker[uid] = payout
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