import os
from decimal import Decimal

from core import participation_policy, participation_service


def test_activation_defaults_to_disabled(monkeypatch):
    for name in (
        "SLH_PARTICIPATION_ENABLED",
        "SLH_PARTICIPATION_POLICY_APPROVED",
        "SLH_PARTICIPATION_ACCOUNTING_APPROVED",
        "SLH_PARTICIPATION_LEGAL_APPROVED",
    ):
        monkeypatch.delenv(name, raising=False)
    status = participation_policy.activation_status()
    assert status["active"] is False
    assert status["status"] == "DISABLED"


def test_preview_distribution_is_pure(monkeypatch):
    result = participation_service.preview_distribution("1122", "122", "1000")
    assert result["net_revenue"] == Decimal("1000.00000000")
    assert result["distributable_pool"] == Decimal("800.00000000")


def test_preview_position_reward_applies_cap():
    result = participation_service.preview_position_reward("100", "1000", "1000", 365)
    assert result["share"] == Decimal("1000.00000000")
    assert result["cap"] == Decimal("65.00000000")
    assert result["allocation"] == Decimal("65.00000000")


def test_mutation_is_blocked_without_all_gates(monkeypatch):
    monkeypatch.delenv("SLH_PARTICIPATION_ENABLED", raising=False)
    monkeypatch.delenv("SLH_PARTICIPATION_POLICY_APPROVED", raising=False)
    monkeypatch.delenv("SLH_PARTICIPATION_ACCOUNTING_APPROVED", raising=False)
    monkeypatch.delenv("SLH_PARTICIPATION_LEGAL_APPROVED", raising=False)
    try:
        participation_service.create_position("u1", "100", request_id="r1")
    except RuntimeError as exc:
        assert str(exc) == "PARTICIPATION_NOT_ACTIVE"
    else:
        raise AssertionError("mutation unexpectedly enabled")
