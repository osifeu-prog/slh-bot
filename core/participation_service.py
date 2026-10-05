"""Disabled-by-default authority for the future SLH Participation product.

This module does not reuse Credits staking. It keeps Participation accounting
separate and requires all activation gates before any mutation is allowed.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_DOWN, InvalidOperation

from core import participation_ledger
from core import participation_policy


MONEY_QUANTUM = Decimal("0.00000001")


def _d(value) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("INVALID_DECIMAL") from exc
    if not result.is_finite():
        raise ValueError("INVALID_DECIMAL")
    return result


def _q(value) -> Decimal:
    return _d(value).quantize(MONEY_QUANTUM, rounding=ROUND_DOWN)


def _maturity(created_at: datetime) -> datetime:
    return created_at + timedelta(days=participation_policy.TERM_DAYS)


def preview_distribution(gross_revenue, operating_costs, participating_total):
    """Pure calculation; never writes state or creates a position."""
    gross = _d(gross_revenue)
    costs = _d(operating_costs)
    total = _d(participating_total)
    if gross < 0 or costs < 0 or total < 0:
        raise ValueError("NEGATIVE_VALUE")
    net = max(gross - costs, Decimal("0"))
    pool = _q(net * _d(participation_policy.DISTRIBUTION_RATIO))
    return {
        "gross_revenue": _q(gross),
        "operating_costs": _q(costs),
        "net_revenue": _q(net),
        "distribution_ratio": participation_policy.DISTRIBUTION_RATIO,
        "distributable_pool": pool,
        "participating_total": _q(total),
    }


def preview_position_reward(
    position_amount, distributable_pool, total_participating, elapsed_days
):
    """Pure proportional allocation with annual cap; never writes state."""
    principal = _d(position_amount)
    pool = _d(distributable_pool)
    total = _d(total_participating)
    days = int(elapsed_days)
    if principal <= 0 or pool < 0 or total <= 0 or days < 0:
        raise ValueError("INVALID_REWARD_INPUT")
    share = pool * principal / total
    cap = (
        principal
        * _d(participation_policy.ANNUAL_CAP_RATIO)
        * _d(days)
        / Decimal("365")
    )
    allocation = min(share, cap)
    return {
        "principal": _q(principal),
        "share": _q(share),
        "cap": _q(cap),
        "allocation": _q(allocation),
        "elapsed_days": days,
    }


def create_position(participant_id, principal, *, request_id):
    """Create position metadata only; activation is disabled by default.

    A future asset-lock adapter must be integrated before activation is approved.
    This function never moves an existing wallet balance.
    """
    participation_policy.require_active()
    participant_id = str(participant_id).strip()
    request_id = str(request_id).strip()
    principal_d = _q(principal)
    if not participant_id or not request_id or principal_d <= 0:
        raise ValueError("INVALID_POSITION")

    position_id = f"participation:{participant_id}:{request_id}"
    now = datetime.now(timezone.utc)

    def mutate(data):
        existing = data["positions"].get(position_id)
        if existing:
            return {"status": "duplicate", "position": existing}
        position = {
            "position_id": position_id,
            "participant_id": participant_id,
            "asset": participation_policy.ASSET,
            "principal": float(principal_d),
            "created_at": now.isoformat(),
            "maturity_at": _maturity(now).isoformat(),
            "status": "FUNDING_PENDING",
            "eligibility_state": "PENDING_ASSET_LOCK",
            "policy_version": participation_policy.POLICY_VERSION,
            "request_id": request_id,
        }
        data["positions"][position_id] = position
        participation_ledger.append_audit(
            data, event="POSITION_CREATED", event_id=position_id, payload=position
        )
        return {"status": "created", "position": position}

    return participation_ledger.update(mutate)


def record_reward_batch(
    *,
    source_revenue_id,
    gross_revenue,
    operating_costs,
    allocations,
    approval_state,
    idempotency_key,
):
    """Record a bounded reward batch without touching existing wallets.

    One source revenue event may be allocated across multiple positions. The
    batch total cannot exceed the policy-defined distributable pool or any
    position's elapsed-time annual cap.
    """
    participation_policy.require_active()
    source_revenue_id = str(source_revenue_id).strip()
    idempotency_key = str(idempotency_key).strip()
    if not source_revenue_id or not idempotency_key:
        raise ValueError("INVALID_REWARD_BATCH")
    if not isinstance(allocations, list) or not allocations:
        raise ValueError("INVALID_REWARD_ALLOCATIONS")

    preview = preview_distribution(gross_revenue, operating_costs, "1")
    pool = preview["distributable_pool"]
    batch_id = f"distribution:{source_revenue_id}:{idempotency_key}"

    def mutate(data):
        existing = data["revenue_pools"].get(batch_id)
        if existing:
            return {"status": "duplicate", "distribution": existing}

        total_allocation = Decimal("0")
        reward_rows = []
        seen_positions = set()
        now = datetime.now(timezone.utc)

        for allocation in allocations:
            if not isinstance(allocation, dict):
                raise ValueError("INVALID_REWARD_ALLOCATION")

            position_id = str(allocation.get("position_id", "")).strip()
            amount = _q(allocation.get("amount", 0))
            if not position_id or amount < 0 or position_id in seen_positions:
                raise ValueError("INVALID_REWARD_ALLOCATION")

            position = data["positions"].get(position_id)
            if not position:
                raise ValueError("POSITION_NOT_FOUND")
            if position.get("status") != "ACTIVE":
                raise ValueError("POSITION_NOT_ACTIVE")

            created = datetime.fromisoformat(position["created_at"])
            elapsed_days = max((now - created).days, 0)
            cap = _q(
                _d(position["principal"])
                * _d(participation_policy.ANNUAL_CAP_RATIO)
                * _d(elapsed_days)
                / Decimal("365")
            )
            if amount > cap:
                raise ValueError("POSITION_ANNUAL_CAP_EXCEEDED")

            total_allocation += amount
            seen_positions.add(position_id)
            reward_id = f"reward:{batch_id}:{position_id}"
            reward_rows.append(
                {
                    "reward_id": reward_id,
                    "position_id": position_id,
                    "participant_id": str(position["participant_id"]),
                    "source_revenue_id": source_revenue_id,
                    "amount": float(amount),
                    "calculation_basis": {
                        "gross_revenue": float(preview["gross_revenue"]),
                        "operating_costs": float(preview["operating_costs"]),
                        "net_revenue": float(preview["net_revenue"]),
                        "distributable_pool": float(pool),
                        "elapsed_days": elapsed_days,
                        "annual_cap": float(cap),
                    },
                    "approval_state": str(approval_state),
                    "policy_version": participation_policy.POLICY_VERSION,
                    "idempotency_key": f"{idempotency_key}:{position_id}",
                    "status": "ACCRUED",
                    "timestamp": now.isoformat(),
                }
            )

        total_allocation = _q(total_allocation)
        if total_allocation > pool:
            raise ValueError("DISTRIBUTION_POOL_EXCEEDED")

        distribution = {
            "distribution_id": batch_id,
            "source_revenue_id": source_revenue_id,
            "gross_revenue": float(preview["gross_revenue"]),
            "operating_costs": float(preview["operating_costs"]),
            "net_revenue": float(preview["net_revenue"]),
            "distributable_pool": float(pool),
            "allocated_total": float(total_allocation),
            "unallocated": float(_q(pool - total_allocation)),
            "approval_state": str(approval_state),
            "policy_version": participation_policy.POLICY_VERSION,
            "idempotency_key": idempotency_key,
            "timestamp": now.isoformat(),
            "status": "RECORDED",
        }
        data["revenue_pools"][batch_id] = distribution

        for reward in reward_rows:
            data["reward_events"][reward["reward_id"]] = reward
            participation_ledger.append_audit(
                data,
                event="REWARD_RECORDED",
                event_id=reward["reward_id"],
                payload=reward,
            )

        participation_ledger.append_audit(
            data,
            event="DISTRIBUTION_RECORDED",
            event_id=batch_id,
            payload=distribution,
        )
        return {
            "status": "recorded",
            "distribution": distribution,
            "rewards": reward_rows,
        }

    return participation_ledger.update(mutate)


def settle_position(position_id, *, settlement_id):
    participation_policy.require_active()
    position_id = str(position_id).strip()
    settlement_id = str(settlement_id).strip()
    if not position_id or not settlement_id:
        raise ValueError("INVALID_SETTLEMENT")

    def mutate(data):
        position = data["positions"].get(position_id)
        if not position:
            raise ValueError("POSITION_NOT_FOUND")

        now = datetime.now(timezone.utc)
        maturity = datetime.fromisoformat(position["maturity_at"])
        if now < maturity:
            raise ValueError("PARTICIPATION_LOCKED")
        if position.get("status") not in {"ACTIVE", "MATURED"}:
            raise ValueError("INVALID_POSITION_STATE")

        existing = data["settlements"].get(settlement_id)
        if existing:
            return {"status": "duplicate", "settlement": existing}

        settlement = {
            "settlement_id": settlement_id,
            "position_id": position_id,
            "participant_id": position["participant_id"],
            "asset": position["asset"],
            "timestamp": now.isoformat(),
            "status": "PENDING_APPROVED_PATH",
            "policy_version": participation_policy.POLICY_VERSION,
        }
        position["status"] = "MATURED"
        data["settlements"][settlement_id] = settlement
        participation_ledger.append_audit(
            data,
            event="POSITION_MATURED",
            event_id=settlement_id,
            payload=settlement,
        )
        return {"status": "matured", "settlement": settlement}

    return participation_ledger.update(mutate)
