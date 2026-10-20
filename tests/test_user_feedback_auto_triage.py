from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

import handlers.user_feedback_handler as target


def _base_db():
    return {
        "users": {"123": {"wallet": {"credits": 42.0, "staked": 5.0}}},
        "ledger": [{"uid": "123", "before": 42.0, "amount": 0.0, "after": 42.0, "reason": "baseline"}],
        "settings": {"SLH_EXCHANGE_PUBLIC_OPEN": "0"},
        "user_feedback": [],
        "bug_triage_tasks": [],
    }


def _install_atomic(monkeypatch, db):
    monkeypatch.setattr(
        target.state_manager,
        "atomic_update",
        lambda mutator: mutator(db),
    )


def _exchange_check(*, ok=False, gate="CLOSED", ready=False):
    return {
        "ok": ok,
        "public_gate": gate,
        "public_ready": ready,
        "verdict": "OPEN" if ok else "BLOCKED",
        "detail": "account_ledger=BLOCKED(ACCOUNT_LEDGER_SEQUENCE_DISCONTINUITY)",
        "account_ledger_status": "BLOCKED",
        "account_ledger_blockers": ["ACCOUNT_LEDGER_SEQUENCE_DISCONTINUITY"],
    }


def test_exchange_bug_report_creates_task_with_read_only_current_exchange_evidence(monkeypatch):
    db = _base_db()
    before_money = deepcopy({"users": db["users"], "ledger": db["ledger"], "settings": db["settings"]})
    _install_atomic(monkeypatch, db)
    with patch("core.system_checks.check_exchange", return_value=_exchange_check()):
        result = target._record(
            "123", "tester", "Tester",
            "כשמנסים לקנות SLH מופיעה הודעה שאין הרשאה", "bug",
        )

    entry = db["user_feedback"][0]
    task = db["bug_triage_tasks"][0]
    assert result["ok"] is True
    assert entry["triage"]["component"] == "exchange"
    assert entry["triage"]["priority"] == "P1"
    assert entry["triage"]["diagnostic"]["status"] == "BLOCKED"
    assert entry["triage"]["diagnostic"]["evidence"]["public_gate"] == "CLOSED"
    assert task["id"] == "BUGTASK_000001"
    assert task["report_ids"] == [1]
    assert task["status"] == "OPEN"
    assert {"users": db["users"], "ledger": db["ledger"], "settings": db["settings"]} == before_money


def test_identical_open_bug_reports_link_to_one_idempotent_task(monkeypatch):
    db = _base_db()
    _install_atomic(monkeypatch, db)
    with patch("core.system_checks.check_exchange", return_value=_exchange_check()):
        first = target._record("123", "tester", "Tester", "Exchange buy blocked", "bug")
        second = target._record("456", "other", "Other", "Exchange buy blocked", "bug")

    assert first["triage"]["task_id"] == second["triage"]["task_id"]
    assert len(db["bug_triage_tasks"]) == 1
    assert db["bug_triage_tasks"][0]["report_ids"] == [1, 2]
    assert db["bug_triage_tasks"][0]["duplicate_count"] == 1
    assert len(db["user_feedback"]) == 2


def test_payment_reports_do_not_execute_claim_refund_or_gate_mutations(monkeypatch):
    db = _base_db()
    before_money = deepcopy({"users": db["users"], "ledger": db["ledger"], "settings": db["settings"]})
    _install_atomic(monkeypatch, db)
    triage = target._triage_report("Stars payment was not credited; please refund", "bug")
    result = target._record("123", "", "", "Stars payment was not credited; please refund", "bug", triage=triage)

    assert result["triage"]["component"] == "payments"
    assert result["triage"]["diagnostic"]["status"] == "UNKNOWN"
    assert result["triage"]["diagnostic"]["check"] == "payment_diagnostic_not_auto_executed"
    assert {"users": db["users"], "ledger": db["ledger"], "settings": db["settings"]} == before_money


def test_exchange_diagnostic_exception_degrades_to_unknown(monkeypatch):
    with patch("core.system_checks.check_exchange", side_effect=RuntimeError("sensitive details omitted")):
        triage = target._triage_report("Buy SLH exchange", "bug")
    assert triage["component"] == "exchange"
    assert triage["diagnostic"]["status"] == "UNKNOWN"
