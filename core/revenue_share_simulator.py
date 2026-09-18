"""Pure, read-only simulator for the future SLH participation product.

This module intentionally has no dependency on state_manager, wallets, staking,
payments, Telegram handlers, or the production database. It is suitable for
unit tests, Control Plane previews, and offline scenario analysis.

It does not accept funds, create positions, accrue balances, or settle claims.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN, InvalidOperation
from typing import Iterable


MONEY_QUANTUM = Decimal("0.01")


def D(value) -> Decimal:
    """Convert supported numeric/string input to an exact Decimal."""
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("INVALID_DECIMAL") from exc


def money(value: Decimal) -> Decimal:
    return D(value).quantize(MONEY_QUANTUM, rounding=ROUND_DOWN)


@dataclass(frozen=True)
class RevenuePeriod:
    period_id: str
    gross_revenue: Decimal
    operating_costs: Decimal
    reserve_ratio: Decimal = Decimal("0.80")

    @property
    def net_revenue(self) -> Decimal:
        return max(Decimal("0"), self.gross_revenue - self.operating_costs)

    @property
    def distributable_pool(self) -> Decimal:
        return money(self.net_revenue * self.reserve_ratio)


@dataclass(frozen=True)
class Lot:
    position_id: str
    participant_id: str
    principal: Decimal
    active: bool = True


def validate_period(period: RevenuePeriod) -> None:
    if not period.period_id.strip():
        raise ValueError("INVALID_PERIOD_ID")
    if period.gross_revenue < 0:
        raise ValueError("NEGATIVE_GROSS_REVENUE")
    if period.operating_costs < 0:
        raise ValueError("NEGATIVE_OPERATING_COSTS")
    if not (Decimal("0") <= period.reserve_ratio <= Decimal("1")):
        raise ValueError("INVALID_RESERVE_RATIO")


def eligible_lots(lots: Iterable[Lot]) -> list[Lot]:
    result = []
    for lot in lots:
        if lot.active and lot.principal > 0:
            result.append(lot)
    return result


def pro_rata_distribution(
    period: RevenuePeriod,
    lots: Iterable[Lot],
) -> dict:
    """Return a deterministic hypothetical distribution; never writes state."""
    validate_period(period)
    eligible = eligible_lots(lots)
    pool = period.distributable_pool
    total_principal = sum((D(l.principal) for l in eligible), Decimal("0"))

    if not eligible or total_principal <= 0 or pool <= 0:
        return {
            "period_id": period.period_id,
            "gross_revenue": money(period.gross_revenue),
            "operating_costs": money(period.operating_costs),
            "net_revenue": money(period.net_revenue),
            "reserve_ratio": period.reserve_ratio,
            "distributable_pool": pool,
            "total_principal": money(total_principal),
            "allocations": {},
            "allocated_total": Decimal("0.00"),
            "unallocated": pool,
        }

    allocations = {}
    allocated = Decimal("0")
    for lot in eligible:
        raw = pool * D(lot.principal) / total_principal
        amount = money(raw)
        allocations[lot.position_id] = {
            "participant_id": lot.participant_id,
            "principal": money(lot.principal),
            "amount": amount,
        }
        allocated += amount

    # Keep the simulator conservative: rounding remainder stays unallocated
    # rather than being silently assigned to a participant.
    unallocated = money(pool - allocated)
    return {
        "period_id": period.period_id,
        "gross_revenue": money(period.gross_revenue),
        "operating_costs": money(period.operating_costs),
        "net_revenue": money(period.net_revenue),
        "reserve_ratio": period.reserve_ratio,
        "distributable_pool": pool,
        "total_principal": money(total_principal),
        "allocations": allocations,
        "allocated_total": money(allocated),
        "unallocated": unallocated,
    }


def apply_annual_cap(
    allocation: Decimal,
    principal: Decimal,
    elapsed_days: int,
    annual_cap: Decimal = Decimal("0.65"),
) -> Decimal:
    """Apply a mathematical cap to a hypothetical payout only.

    The cap is a simulation parameter, not a promise or legal classification.
    """
    if elapsed_days < 0:
        raise ValueError("INVALID_ELAPSED_DAYS")
    if principal < 0:
        raise ValueError("INVALID_PRINCIPAL")
    if annual_cap < 0:
        raise ValueError("INVALID_ANNUAL_CAP")

    years = D(elapsed_days) / Decimal("365")
    cap = D(principal) * annual_cap * years
    return money(min(D(allocation), cap))


def capped_distribution(
    period: RevenuePeriod,
    lots: Iterable[Lot],
    elapsed_days_by_position: dict[str, int],
    annual_cap: Decimal = Decimal("0.65"),
) -> dict:
    base = pro_rata_distribution(period, lots)
    allocations = {}
    allocated = Decimal("0")

    for position_id, item in base["allocations"].items():
        capped = apply_annual_cap(
            item["amount"],
            item["principal"],
            elapsed_days_by_position.get(position_id, 0),
            annual_cap,
        )
        allocations[position_id] = {**item, "amount": capped}
        allocated += capped

    allocated = money(allocated)
    return {
        **base,
        "annual_cap": D(annual_cap),
        "allocations": allocations,
        "allocated_total": allocated,
        "unallocated": money(base["distributable_pool"] - allocated),
    }


def simulate_periods(periods: Iterable[RevenuePeriod]) -> dict:
    """Reject duplicate period IDs; no persistence is involved."""
    seen = set()
    results = []
    for period in periods:
        validate_period(period)
        if period.period_id in seen:
            raise ValueError("DUPLICATE_PERIOD_ID")
        seen.add(period.period_id)
        results.append({
            "period_id": period.period_id,
            "net_revenue": money(period.net_revenue),
            "distributable_pool": period.distributable_pool,
        })
    return {"periods": results, "period_count": len(results)}
