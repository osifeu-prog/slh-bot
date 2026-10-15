from types import SimpleNamespace
from unittest.mock import patch

from handlers import system_checks_handler as target


class FakeBot:
    def __init__(self):
        self.handlers = {}
        self.replies = []

    def message_handler(self, commands=None, **kwargs):
        def decorator(handler):
            for command in commands or []:
                self.handlers[str(command).lstrip("/")] = handler
            return handler
        return decorator

    def reply_to(self, message, text, **kwargs):
        self.replies.append(str(text))


def _report():
    finding = {
        "code": "MANUAL_RESERVE_CORRECTION_REQUIRES_REVIEW",
        "ledger": "slh_token_ledger",
        "order_id": "O0000000009",
        "event_ids": ["correction:missed_release:O0000000009"],
        "correction_delta": "10000",
        "operational_classification": "HISTORICAL_ARCHIVED_TEST_SEED",
        "uid_suffix": "1391",
        "note": "Manual correction requires accounting review.",
    }
    return {
        "read_only": True,
        "status": "FAIL",
        "operational_status": "PASS",
        "release_readiness_status": "BLOCKED",
        "release_blocking_finding_count": 1,
        "release_blocking_findings": [finding],
        "checked_cancelled_sell_orders": 5,
        "finding_count": 7,
        "findings": [finding],
    }


def test_exchange_reserve_report_displays_order_level_release_findings():
    rendered = target._exchange_reserves_output(_report())

    assert "Release readiness: BLOCKED" in rendered
    assert "order=O0000000009" in rendered
    assert "MANUAL_RESERVE_CORRECTION_REQUIRES_REVIEW" in rendered
    assert "correction=10000" in rendered
    assert "HISTORICAL_ARCHIVED_TEST_SEED" in rendered
    assert "uid=5010371391" not in rendered
    assert "No balances, orders, ledgers, wallets, or gates were changed." in rendered


def test_exchange_reserve_report_fails_closed_on_malformed_result():
    rendered = target._exchange_reserves_output({
        "release_readiness_status": "PASS",
        "release_blocking_finding_count": 0,
    })

    assert "Release readiness: BLOCKED" in rendered
    assert "Audit integrity: BLOCKED" in rendered
    assert "RESERVE_AUDIT_RESULT_INVALID" in rendered


def test_exchange_reserve_command_uses_read_only_audit_and_authorization():
    bot = FakeBot()
    target.register(bot)
    handler = bot.handlers["check_exchange_reserves"]
    message = SimpleNamespace(from_user=SimpleNamespace(id=8789977826), text="/check_exchange_reserves")

    with patch.object(target, "_allowed", return_value=True), patch(
        "core.slh_exchange_reconciliation.run_once",
        return_value=_report(),
    ) as audit:
        handler(message)

    audit.assert_called_once_with()
    assert "O0000000009" in bot.replies[-1]


def test_exchange_reserve_command_does_not_audit_for_unauthorized_user():
    bot = FakeBot()
    target.register(bot)
    handler = bot.handlers["check_exchange_reserves"]
    message = SimpleNamespace(from_user=SimpleNamespace(id=123), text="/check_exchange_reserves")

    with patch.object(target, "_allowed", return_value=False), patch.object(
        target, "_send_denied"
    ) as denied, patch(
        "core.slh_exchange_reconciliation.run_once"
    ) as audit:
        handler(message)

    denied.assert_called_once()
    audit.assert_not_called()

def test_exchange_reserve_report_fails_closed_when_blocker_count_conflicts_with_findings():
    report = _report()
    report["release_readiness_status"] = "PASS"
    report["release_blocking_finding_count"] = 0

    rendered = target._exchange_reserves_output(report)

    assert "Release readiness: BLOCKED" in rendered
    assert "Audit integrity: BLOCKED" in rendered
    assert "RESERVE_AUDIT_COUNT_MISMATCH" in rendered
