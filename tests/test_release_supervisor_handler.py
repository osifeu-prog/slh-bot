from types import SimpleNamespace

import handlers.releasecheck_handler as handler


class FakeBot:
    def __init__(self):
        self.registered = []
        self.replies = []

    def message_handler(self, commands=None, **kwargs):
        def decorate(fn):
            self.registered.append((commands or [], fn))
            return fn
        return decorate

    def reply_to(self, message, text, **kwargs):
        self.replies.append((message, text))


def _registered_command(bot, name):
    return next(
        fn
        for commands, fn in bot.registered
        if name in commands
    )


def _mock_release_reports(monkeypatch, exchange):
    monkeypatch.setattr(handler, "is_owner", lambda uid: str(uid) == "8789977826")
    monkeypatch.setattr(
        handler,
        "build_release_report",
        lambda: {
            "overall_status": "BLOCKED",
            "checks": {
                "Internal exchange": {
                    "status": "BLOCKED",
                    "detail": "canonical exchange verdict=BLOCKED; account_ledger=BLOCKED",
                },
            },
            "blockers": ["Internal exchange: account ledger remains blocked"],
        },
    )
    monkeypatch.setattr(
        handler,
        "build_recovery_center_report",
        lambda release_report: {
            "overall_status": "BLOCKED",
            "account_ledger": {
                "status": "BLOCKED",
                "unresolved_continuity_break_count": 2,
                "current_balance_matches_tail": True,
            },
            "blockers": [{
                "id": "LEDGER-EXAMPLE",
                "summary": "Credits ledger sequence gap requires evidence",
                "next_action": "Locate independent source evidence; do not insert synthetic rows.",
            }],
            "review_items": [],
        },
    )
    monkeypatch.setattr(handler, "check_exchange", lambda: exchange)


def test_release_supervisor_alias_is_registered_and_shows_canonical_status(monkeypatch):
    bot = FakeBot()
    handler.register(bot)
    handler_fn = _registered_command(bot, "release")
    _mock_release_reports(monkeypatch, {
        "verdict": "BLOCKED",
        "public_ready": False,
        "public_gate": "CLOSED",
        "reserve_reconciliation_status": "PASS",
        "reserve_blocking_count": 0,
        "reserve_blocking_codes": [],
    })

    message = SimpleNamespace(
        text="/release",
        from_user=SimpleNamespace(id=8789977826),
    )
    handler_fn(message)
    output = bot.replies[-1][1]

    assert "SLH Release Supervisor — BLOCKED · READ ONLY" in output
    assert "Exchange snapshot: verdict=BLOCKED · readiness=FAIL" in output
    assert "Reserve reconciliation: PASS · findings=0 · codes=NONE" in output
    assert "Public trading gate: CLOSED" in output
    assert "Account ledger: BLOCKED · unresolved gaps=2 · balance matches tail=True" in output
    assert "LEDGER-EXAMPLE" in output
    assert "no balances, ledger rows, orders, or BNB/TON/Exchange gates are changed" in output


def test_release_supervisor_fails_closed_on_blocked_reserve_report_without_codes(monkeypatch):
    bot = FakeBot()
    handler.register(bot)
    handler_fn = _registered_command(bot, "release_supervisor")
    _mock_release_reports(monkeypatch, {
        "verdict": "BLOCKED",
        "public_ready": False,
        "public_gate": "CLOSED",
        "reserve_reconciliation_status": "BLOCKED",
        "reserve_blocking_count": 1,
        "reserve_blocking_codes": [],
    })

    message = SimpleNamespace(
        text="/release_supervisor",
        from_user=SimpleNamespace(id=8789977826),
    )
    handler_fn(message)
    output = bot.replies[-1][1]

    assert "SLH Release Supervisor — BLOCKED · READ ONLY" in output
    assert "Reserve reconciliation: BLOCKED" in output
    assert "RESERVE_AUDIT_RESULT_INVALID" in output
    assert "Public trading gate: CLOSED" in output


def test_release_supervisor_remains_owner_only(monkeypatch):
    bot = FakeBot()
    handler.register(bot)
    handler_fn = _registered_command(bot, "release")

    monkeypatch.setattr(handler, "is_owner", lambda uid: False)
    def fail_if_called():
        raise AssertionError("release report must not run for a non-owner")
    monkeypatch.setattr(handler, "build_release_report", fail_if_called)

    message = SimpleNamespace(
        text="/release",
        from_user=SimpleNamespace(id=111),
    )
    handler_fn(message)

    assert "Owner only" in bot.replies[-1][1]
