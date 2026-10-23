from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core import periodic_release_audit as target


OWNER_UID = "8789977826"
COMMIT = "a" * 40


def _db():
    return {
        "users": {OWNER_UID: {"wallet": {"credits": 3.0}}},
        "transactions": {},
        "ledger": [
            {
                "uid": OWNER_UID,
                "before": 1.0,
                "amount": 2.0,
                "after": 3.0,
                "reason": "store:purchase",
                "meta": {"event_id": "owner-event-1"},
            },
        ],
    }


def _ledger_result():
    return {
        "scope": "read_only",
        "status": "PASS",
        "rows_checked": 1,
        "credits_sequence_rows_checked": 1,
        "non_credits_rows_skipped": 0,
        "continuity_break_count": 0,
        "observed_discontinuity_count": 0,
        "resolved_gap_count": 0,
        "unresolved_continuity_break_count": 0,
        "arithmetic_error_count": 0,
        "malformed_global_rows": 0,
        "current_balance_matches_tail": True,
        "finding_count": 0,
        "blocking_finding_count": 0,
        "findings": [],
        "findings_truncated": False,
        "blockers": [],
        "financial_mutation_performed": False,
        "gate_changed": False,
    }


def _release_result(status="DEGRADED"):
    check_names = {
        "Telegram runtime",
        "AI intake",
        "Mini App auth",
        "Internal exchange",
        "Stars revenue",
        "External settlement gates",
        "Participation",
    }
    checks = {
        name: {"status": "GREEN", "detail": f"{name} test result"}
        for name in check_names
    }
    if status == "DEGRADED":
        checks["Internal exchange"] = {
            "status": "DEGRADED",
            "detail": "public gate=CLOSED; owner approval remains required",
        }
    elif status == "BLOCKED":
        checks["Internal exchange"] = {
            "status": "BLOCKED",
            "detail": "owner ledger blocker",
        }
    return {
        "overall_status": status,
        "checks": checks,
        "blockers": ["Internal exchange: owner ledger blocker"] if status == "BLOCKED" else [],
    }


def _exchange_result():
    return {
        "verdict": "READY_TO_OPEN",
        "public_gate": "CLOSED",
        "public_ready": True,
        "account_ledger_status": "PASS",
        "account_ledger_integrity": True,
    }


def _patch_identity(monkeypatch):
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", COMMIT)
    monkeypatch.setenv("RAILWAY_DEPLOYMENT_ID", "deployment-123")
    monkeypatch.setenv("RAILWAY_SERVICE_ID", "service-1")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_ID", "environment-1")


def test_automated_report_reads_one_canonical_db_snapshot_without_mutation(monkeypatch):
    _patch_identity(monkeypatch)
    db = _db()
    original = deepcopy(db)

    with patch("state_manager.load_db", return_value=db) as load_db, patch(
        "core.account_ledger_audit.audit_account_ledger",
        return_value=_ledger_result(),
    ) as ledger_audit, patch(
        "core.release_readiness.build_release_report",
        side_effect=lambda db=None: _release_result("DEGRADED"),
    ) as release_report, patch(
        "core.system_checks.check_exchange",
        return_value=_exchange_result(),
    ) as exchange_check:
        report = target.run_once(now_utc="2026-10-24T00:00:00+00:00")

    load_db.assert_called_once()
    ledger_audit.assert_called_once_with(db, target.OWNER_ID)
    release_report.assert_called_once_with(db=db)
    exchange_check.assert_called_once_with(db)
    assert report["schema_version"] == 1
    assert report["checked_at_utc"] == "2026-10-24T00:00:00+00:00"
    assert report["source"]["commit_sha"] == COMMIT
    assert report["source"]["deployment_id"] == "deployment-123"
    assert report["ledger"]["status"] == "PASS"
    assert report["exchange"]["public_gate"] == "CLOSED"
    assert report["status"] == "DEGRADED"
    assert report["financial_mutation_performed"] is False
    assert report["gate_changed"] is False
    assert db == original


def test_automated_report_fails_closed_when_audit_contract_is_malformed(monkeypatch):
    _patch_identity(monkeypatch)
    invalid = _ledger_result()
    invalid["financial_mutation_performed"] = True

    with patch("state_manager.load_db", return_value=_db()), patch(
        "core.account_ledger_audit.audit_account_ledger", return_value=invalid
    ), patch(
        "core.release_readiness.build_release_report",
        side_effect=lambda db=None: _release_result("GREEN"),
    ), patch(
        "core.system_checks.check_exchange", return_value=_exchange_result()
    ):
        report = target.run_once()

    assert report["status"] == "BLOCKED"
    assert report["evidence_integrity"] == "BLOCKED"
    assert "ACCOUNT_LEDGER_AUDIT_RESULT_INVALID" in report["blockers"]


def test_missing_code_or_deployment_identity_fails_closed(monkeypatch):
    monkeypatch.delenv("RAILWAY_GIT_COMMIT_SHA", raising=False)
    monkeypatch.delenv("GIT_COMMIT_SHA", raising=False)
    monkeypatch.delenv("COMMIT_SHA", raising=False)
    monkeypatch.delenv("RAILWAY_DEPLOYMENT_ID", raising=False)
    monkeypatch.delenv("SLH_DEPLOYMENT_ID", raising=False)

    with patch("state_manager.load_db", return_value=_db()), patch(
        "core.account_ledger_audit.audit_account_ledger", return_value=_ledger_result()
    ), patch(
        "core.release_readiness.build_release_report",
        side_effect=lambda db=None: _release_result("GREEN"),
    ), patch(
        "core.system_checks.check_exchange", return_value=_exchange_result()
    ):
        report = target.run_once()

    assert report["status"] == "BLOCKED"
    assert report["source"]["commit_sha"] == "UNKNOWN"
    assert report["source"]["deployment_id"] == "UNKNOWN"
    assert "CODE_COMMIT_IDENTITY_UNAVAILABLE" in report["blockers"]
    assert "DEPLOYMENT_IDENTITY_UNAVAILABLE" in report["blockers"]


def test_notification_is_sent_once_per_changed_blocker_signature():
    class FakeBot:
        def __init__(self):
            self.messages = []

        def send_message(self, **kwargs):
            self.messages.append(kwargs)

    logs = []
    bot = FakeBot()
    report = {
        "status": "BLOCKED",
        "evidence_integrity": "PASS",
        "source": {"commit_sha": COMMIT, "deployment_id": "deployment-123"},
        "ledger": {"status": "BLOCKED", "unresolved_continuity_break_count": 3,
                   "arithmetic_error_count": 0, "findings": []},
        "exchange": {"verdict": "BLOCKED", "public_gate": "CLOSED",
                     "account_ledger_status": "BLOCKED"},
        "release_readiness": {"status": "BLOCKED", "checks": {}},
        "blockers": ["ACCOUNT_LEDGER_SEQUENCE_DISCONTINUITY"],
        "evidence_refs": ["/check_owner_ledger"],
        "checked_at_utc": "2026-10-24T00:00:00+00:00",
        "financial_mutation_performed": False,
        "gate_changed": False,
    }

    signature, status = target._deliver_if_changed(report, bot, logs.append)
    same_blocker_later = deepcopy(report)
    same_blocker_later["checked_at_utc"] = "2026-10-24T00:15:00+00:00"
    same_blocker_later["ledger"]["rows_checked"] = 250
    signature_again, status_again = target._deliver_if_changed(
        same_blocker_later, bot, logs.append, signature, status
    )

    assert len(bot.messages) == 1
    assert bot.messages[0]["chat_id"] == int(target.OWNER_ID)
    assert "READ ONLY" in bot.messages[0]["text"]
    assert signature_again == signature
    assert status_again == status

    changed_gap = deepcopy(same_blocker_later)
    changed_gap["ledger"]["findings"] = [{
        "type": "SEQUENCE_GAP_REQUIRES_SOURCE_EVIDENCE",
        "previous_index": 1,
        "next_index": 3,
        "delta_to_explain": 5.0,
        "resolves_gap": False,
        "source_match_status": "CONTEXT_ONLY_REQUIRES_RECONCILIATION",
    }]
    changed_signature, changed_status = target._deliver_if_changed(
        changed_gap, bot, logs.append, signature_again, status_again
    )
    assert len(bot.messages) == 2
    assert "delta=5.0 Credits" in bot.messages[1]["text"]
    assert changed_signature != signature_again
    assert changed_status == "BLOCKED"




def test_release_report_validation_requires_complete_and_consistent_check_set():
    good = _release_result("DEGRADED")
    assert target._valid_release_result(good)

    incomplete = deepcopy(good)
    incomplete["checks"].pop("Stars revenue")
    assert not target._valid_release_result(incomplete)

    inconsistent = deepcopy(good)
    inconsistent["overall_status"] = "GREEN"
    assert not target._valid_release_result(inconsistent)


def test_ledger_pass_requires_tail_match_and_zero_blockers():
    good = _ledger_result()
    assert target._valid_ledger_result(good)

    bad_tail = deepcopy(good)
    bad_tail["current_balance_matches_tail"] = False
    assert not target._valid_ledger_result(bad_tail)

    contradictory = deepcopy(good)
    contradictory["blocking_finding_count"] = 1
    assert not target._valid_ledger_result(contradictory)


def test_periodic_worker_notifies_owner_when_audit_raises():
    class FakeBot:
        def __init__(self):
            self.messages = []

        def send_message(self, **kwargs):
            self.messages.append(kwargs)

    class StopLoop(Exception):
        pass

    bot = FakeBot()
    logs = []
    with patch("core.periodic_release_audit.run_once", side_effect=RuntimeError("simulated")), patch(
        "core.periodic_release_audit.time.sleep", side_effect=StopLoop
    ):
        with pytest.raises(StopLoop):
            target.run_periodic(bot, logs.append, interval_seconds=60)

    assert len(bot.messages) == 1
    assert bot.messages[0]["chat_id"] == int(target.OWNER_ID)
    assert "AUDIT_WORKER_EXCEPTION:RuntimeError" in bot.messages[0]["text"]
    assert "status=BLOCKED" in "\n".join(logs)



class FakeBot:
    def __init__(self):
        self.handlers = {}
        self.replies = []

    def message_handler(self, commands=None, **_kwargs):
        def decorate(function):
            for command in commands or []:
                self.handlers[command] = function
            return function
        return decorate

    def reply_to(self, message, text, **_kwargs):
        self.replies.append((message, str(text)))


def _message(uid=OWNER_UID, chat_type="private"):
    return SimpleNamespace(
        from_user=SimpleNamespace(id=int(uid)),
        chat=SimpleNamespace(type=chat_type),
        text="/release_audit",
    )


def test_manual_command_is_owner_only_and_private(monkeypatch):
    from handlers import system_checks_handler

    bot = FakeBot()
    monkeypatch.setattr(system_checks_handler, "is_owner", lambda uid: str(uid) == OWNER_UID)
    system_checks_handler.register(bot)
    command = bot.handlers["release_audit"]

    with patch("core.periodic_release_audit.run_once") as run_once:
        command(_message(uid="5010371391"))
        run_once.assert_not_called()
    assert "OWNER ONLY" in bot.replies[-1][1]

    with patch("core.periodic_release_audit.run_once") as run_once:
        command(_message(chat_type="group"))
        run_once.assert_not_called()
    assert "שיחה פרטית" in bot.replies[-1][1]
