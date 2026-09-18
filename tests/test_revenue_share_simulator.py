from decimal import Decimal

import pytest

from core.revenue_share_simulator import (
    D,
    Lot,
    RevenuePeriod,
    apply_annual_cap,
    capped_distribution,
    pro_rata_distribution,
    simulate_periods,
)


def test_net_revenue_and_80_percent_pool():
    p = RevenuePeriod("2026-Q3", D("1000"), D("250"))
    assert p.net_revenue == D("750")
    assert p.distributable_pool == D("600")


def test_negative_net_revenue_has_zero_pool():
    p = RevenuePeriod("loss", D("100"), D("250"))
    assert p.net_revenue == D("0")
    assert p.distributable_pool == D("0")


def test_pro_rata_is_deterministic_and_keeps_rounding_remainder():
    p = RevenuePeriod("p1", D("100"), D("0"), D("0.80"))
    lots = [
        Lot("a", "u1", D("1")),
        Lot("b", "u2", D("2")),
    ]
    result = pro_rata_distribution(p, lots)
    assert result["allocations"]["a"]["amount"] == D("26.66")
    assert result["allocations"]["b"]["amount"] == D("53.33")
    assert result["allocated_total"] == D("79.99")
    assert result["unallocated"] == D("0.01")


def test_inactive_and_zero_lots_are_excluded():
    p = RevenuePeriod("p1", D("100"), D("0"))
    lots = [
        Lot("active", "u1", D("100")),
        Lot("inactive", "u2", D("100"), active=False),
        Lot("zero", "u3", D("0")),
    ]
    result = pro_rata_distribution(p, lots)
    assert set(result["allocations"]) == {"active"}


def test_annual_cap_scales_with_elapsed_days():
    assert apply_annual_cap(D("1000"), D("1000"), 365, D("0.65")) == D("650.00")
    assert apply_annual_cap(D("1000"), D("1000"), 182, D("0.65")) == D("323.83")


def test_capped_distribution_never_exceeds_math_cap():
    p = RevenuePeriod("p1", D("2000"), D("0"))
    lots = [Lot("a", "u1", D("100"))]
    result = capped_distribution(p, lots, {"a": 365}, D("0.65"))
    assert result["allocations"]["a"]["amount"] == D("65.00")


def test_duplicate_period_ids_rejected():
    with pytest.raises(ValueError, match="DUPLICATE_PERIOD_ID"):
        simulate_periods([
            RevenuePeriod("same", D("1"), D("0")),
            RevenuePeriod("same", D("2"), D("0")),
        ])


def test_invalid_ratio_rejected():
    with pytest.raises(ValueError, match="INVALID_RESERVE_RATIO"):
        pro_rata_distribution(
            RevenuePeriod("bad", D("1"), D("0"), D("1.01")),
            [],
        )


def test_simulator_does_not_mutate_lots():
    lots = [Lot("a", "u1", D("100"))]
    before = list(lots)
    pro_rata_distribution(RevenuePeriod("p1", D("100"), D("0")), lots)
    assert lots == before
