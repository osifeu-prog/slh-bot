from pathlib import Path
from unittest.mock import patch

from core.command_registry import _extract_commands


def test_system_check_commands_are_registered_in_source():
    source = Path("handlers/system_checks_handler.py").read_text(encoding="utf-8")
    found = _extract_commands(source)
    assert {"check", "checks", "check_ux", "check_money", "check_bnb", "check_bnb_deposits", "check_owner_ledger", "bnb_reverse_prepare", "bnb_reverse_confirm", "bnb_reverse_cancel", "check_ton", "check_exchange"} <= found


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



def test_check_bnb_exposes_read_only_blocker_diagnostics(monkeypatch):
    import core.bnb_gate as bnb_gate
    import core.system_checks as checks

    monkeypatch.setattr(
        bnb_gate,
        "bnb_readiness",
        lambda: {
            "ready": False,
            "effective_open": False,
            "flag_open": False,
            "confirmations_required": 15,
            "reasons": ["BNB_CANONICAL_TREASURY_MISSING"],
        },
    )
    monkeypatch.setattr(
        bnb_gate,
        "bnb_opening_evidence",
        lambda: {
            "status": "BLOCKED",
            "ready_to_open": False,
            "blockers": ["LIVE_BSC_RPC_UNVERIFIED"],
            "warnings": ["empirical_settlement_reconciliation_pending_or_invalid"],
            "live_rpc": {"status": "FAIL"},
            "next_action": "controlled_empirical_reconciliation_before_opening",
            "empirical_settlement": {},
        },
    )
    monkeypatch.setattr(bnb_gate, "bnb_deposits_open", lambda: False)

    result = checks.check_bnb()

    assert result["public_open"] is False
    assert result["gate_reasons"] == ["BNB_CANONICAL_TREASURY_MISSING"]
    assert result["blockers"] == ["LIVE_BSC_RPC_UNVERIFIED"]
    assert result["warnings"] == ["empirical_settlement_reconciliation_pending_or_invalid"]
    assert result["live_rpc_status"] == "FAIL"
    assert result["next_action"] == "controlled_empirical_reconciliation_before_opening"


def test_infrastructure_snapshot_marks_old_registry_stale(monkeypatch):
    import core.control_center as control_center

    monkeypatch.setattr(
        control_center,
        "_load_registry",
        lambda: {
            "schema_version": "1.0",
            "verified_date_utc": "2000-01-01",
            "canonical": {},
            "railway_projects": [],
            "github_unmapped": [],
        },
    )

    snapshot = control_center.get_infrastructure_snapshot()

    assert snapshot["registry_stale"] is True
    assert snapshot["registry_age_days"] is not None
    assert snapshot["registry_age_days"] > snapshot["registry_stale_after_days"]

def test_check_exchange_blocks_public_readiness_when_account_ledger_is_blocked(monkeypatch):
    import core.exchange_gate as exchange_gate
    import core.system_checks as checks
    import handlers.exchange_handler as exchange_handler

    monkeypatch.setattr(exchange_gate, "public_open", lambda: False)
    monkeypatch.setattr(exchange_handler, "_assert_invariants", lambda db: None)

    db = {
        "users": {"owner-1": {"wallet": {"credits": 8.0}}},
        "ledger": [
            {"uid": "owner-1", "before": 10.0, "amount": -2.0, "after": 8.0,
             "reason": "store:purchase"},
            {"uid": "owner-1", "before": 13.0, "amount": -5.0, "after": 8.0,
             "reason": "store:purchase"},
        ],
        "exchange_orders": {},
        "exchange_trades": [],
        "exchange_requests": {},
    }

    result = checks.check_exchange(db)

    assert result["order_book_integrity"] is True
    assert result["trade_integrity"] is True
    assert result["money_invariants"] is True
    assert result["account_ledger_integrity"] is False
    assert "ACCOUNT_LEDGER_SEQUENCE_DISCONTINUITY" in result["account_ledger_blockers"]
    assert result["public_ready"] is False
    assert result["verdict"] == "BLOCKED"
    assert result["ok"] is False
