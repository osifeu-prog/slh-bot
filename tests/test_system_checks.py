from pathlib import Path
from unittest.mock import patch

from core.command_registry import _extract_commands


def test_system_check_commands_are_registered_in_source():
    source = Path("handlers/system_checks_handler.py").read_text(encoding="utf-8")
    found = _extract_commands(source)
    assert {"check", "checks", "check_ux", "check_money", "check_bnb", "check_ton", "check_exchange"} <= found


def test_miniapp_contract_contains_new_public_shell():
    source = Path("mini_app.html").read_text(encoding="utf-8")
    for marker in ('id="balance"', 'id="move"', 'id="growth"', 'id="investor"', 'id="profile"'):
        assert marker in source


def test_system_check_module_exposes_read_only_contract():
    source = Path("core/system_checks.py").read_text(encoding="utf-8")
    for marker in ("def check_db", "def check_commands", "def check_ux", "def check_money", "def check_bnb", "def check_ton", "def check_exchange"):
        assert marker in source


def test_check_bnb_never_reports_public_open_from_flag_without_revalidated_evidence(monkeypatch):
    import core.bnb_gate as bnb_gate
    import core.system_checks as checks

    monkeypatch.setattr(
        bnb_gate,
        "bnb_readiness",
        lambda: {
            "ready": True,
            "effective_open": True,
            "flag_open": True,
            "confirmations_required": 15,
        },
    )
    monkeypatch.setattr(
        bnb_gate,
        "bnb_opening_evidence",
        lambda: {
            "status": "BLOCKED",
            "ready_to_open": False,
            "gate_open": False,
            "blockers": [],
            "empirical_settlement": {},
        },
    )
    monkeypatch.setattr(bnb_gate, "bnb_deposits_open", lambda: False)

    result = checks.check_bnb()

    assert result["public_open"] is False
    assert result["flag_open"] is True
    assert result["ok"] is False
    assert result["launch_ready"] is False
    assert "BNB_DEPOSITS_OPEN=1" in result["detail"]


def test_check_bnb_does_not_call_closed_pending_proof_ready_for_launch(monkeypatch):
    import core.bnb_gate as bnb_gate
    import core.system_checks as checks

    monkeypatch.setattr(
        bnb_gate,
        "bnb_readiness",
        lambda: {
            "ready": True,
            "effective_open": False,
            "flag_open": False,
            "confirmations_required": 15,
        },
    )
    monkeypatch.setattr(
        bnb_gate,
        "bnb_opening_evidence",
        lambda: {
            "status": "BLOCKED",
            "ready_to_open": False,
            "gate_open": False,
            "blockers": [],
            "warnings": ["empirical_settlement_reconciliation_pending_or_invalid"],
            "empirical_settlement": {},
        },
    )
    monkeypatch.setattr(bnb_gate, "bnb_deposits_open", lambda: False)

    result = checks.check_bnb()

    assert result["public_open"] is False
    assert result["ok"] is False
    assert result["ready"] is True
    assert result["launch_ready"] is False
    assert result["empirical_status"] == "PENDING_EMPIRICAL"


def test_check_bnb_is_green_only_when_public_gate_and_proof_are_valid(monkeypatch):
    import core.bnb_gate as bnb_gate
    import core.system_checks as checks

    monkeypatch.setattr(
        bnb_gate,
        "bnb_readiness",
        lambda: {
            "ready": True,
            "effective_open": True,
            "flag_open": True,
            "confirmations_required": 15,
        },
    )
    monkeypatch.setattr(
        bnb_gate,
        "bnb_opening_evidence",
        lambda: {
            "status": "READY_TO_OPEN",
            "ready_to_open": True,
            "gate_open": True,
            "blockers": [],
            "empirical_settlement": {"status": "PASS"},
        },
    )
    monkeypatch.setattr(bnb_gate, "bnb_deposits_open", lambda: True)

    result = checks.check_bnb()

    assert result["public_open"] is True
    assert result["ok"] is True
    assert result["launch_ready"] is True
    assert result["empirical_status"] == "PASS"
