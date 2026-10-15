from unittest.mock import patch

from core.system_checks import check_exchange, check_exchange_for_execution


def _clean_exchange_db():
    return {
        "users": {},
        "exchange_orders": {},
        "exchange_trades": [],
        "exchange_requests": {},
        "ledger": [],
        "slh_token_ledger": [],
    }


def _blocked_reserve_report():
    finding = {
        "code": "MANUAL_RESERVE_CORRECTION_REQUIRES_REVIEW",
        "order_id": "O0000000009",
        "operational_classification": "HISTORICAL_ARCHIVED_TEST_SEED",
    }
    return {
        "read_only": True,
        "status": "FAIL",
        "operational_status": "PASS",
        "release_readiness_status": "BLOCKED",
        "release_blocking_finding_count": 1,
        "release_blocking_findings": [finding],
        "findings": [finding],
    }


def test_exchange_readiness_blocks_on_unreviewed_historical_reserve_correction():
    db = _clean_exchange_db()
    with patch(
        "core.slh_exchange_reconciliation.audit_db",
        return_value=_blocked_reserve_report(),
    ), patch(
        "handlers.exchange_handler._assert_invariants",
        return_value=None,
    ), patch(
        "core.exchange_gate.public_open",
        return_value=True,
    ):
        result = check_exchange(db)

    assert result["public_gate"] == "OPEN"
    assert result["reserve_reconciliation_status"] == "BLOCKED"
    assert result["reserve_reconciliation_ok"] is False
    assert result["reserve_blocking_count"] == 1
    assert result["public_ready"] is False
    assert result["verdict"] == "BLOCKED"
    assert "reserve_reconciliation=BLOCKED" in result["detail"]


def test_fresh_exchange_execution_stays_blocked_even_if_public_flag_is_open():
    db = _clean_exchange_db()
    with patch(
        "core.slh_exchange_reconciliation.audit_db",
        return_value=_blocked_reserve_report(),
    ), patch(
        "handlers.exchange_handler._assert_invariants",
        return_value=None,
    ), patch(
        "core.exchange_gate.public_open",
        return_value=True,
    ):
        result = check_exchange_for_execution(db)

    assert result["public_gate"] == "OPEN"
    assert result["reserve_reconciliation_ok"] is False
    assert result["execution_ready"] is False
    assert result["ok"] is False
    assert result["verdict"] == "BLOCKED"


def test_exchange_readiness_fails_closed_if_reserve_audit_raises():
    db = _clean_exchange_db()
    with patch(
        "core.slh_exchange_reconciliation.audit_db",
        side_effect=RuntimeError("fixture"),
    ), patch(
        "handlers.exchange_handler._assert_invariants",
        return_value=None,
    ), patch(
        "core.exchange_gate.public_open",
        return_value=True,
    ):
        result = check_exchange(db)

    assert result["reserve_reconciliation_status"] == "BLOCKED"
    assert result["reserve_reconciliation_ok"] is False
    assert result["verdict"] == "BLOCKED"

def test_exchange_readiness_fails_closed_on_inconsistent_reserve_summary():
    db = _clean_exchange_db()
    finding = {
        "code": "MANUAL_RESERVE_CORRECTION_REQUIRES_REVIEW",
        "order_id": "O0000000009",
    }
    malformed_report = {
        "read_only": True,
        "release_readiness_status": "PASS",
        "release_blocking_finding_count": 0,
        "release_blocking_findings": [finding],
    }

    with patch(
        "core.slh_exchange_reconciliation.audit_db",
        return_value=malformed_report,
    ), patch(
        "handlers.exchange_handler._assert_invariants",
        return_value=None,
    ), patch(
        "core.exchange_gate.public_open",
        return_value=True,
    ):
        result = check_exchange(db)

    assert result["reserve_reconciliation_status"] == "BLOCKED"
    assert result["reserve_reconciliation_ok"] is False
    assert result["reserve_blocking_count"] == 1
    assert result["public_ready"] is False
    assert result["verdict"] == "BLOCKED"
