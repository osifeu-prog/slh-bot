from types import SimpleNamespace
from unittest.mock import patch

from handlers import system_checks_handler as target


OWNER_UID = "8789977826"


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

    def reply_to(self, _message, text, **_kwargs):
        self.replies.append(str(text))


def _message(text="/check_owner_ledger", *, uid=OWNER_UID, chat_type="private"):
    return SimpleNamespace(
        from_user=SimpleNamespace(id=int(uid)),
        chat=SimpleNamespace(type=chat_type),
        text=text,
    )


def _register(monkeypatch, *, owner_uid=OWNER_UID):
    monkeypatch.setattr(target, "is_owner", lambda uid: str(uid) == owner_uid)
    bot = FakeBot()
    target.register(bot)
    return bot


def test_owner_ledger_command_reports_only_the_private_owner_scope(monkeypatch):
    bot = _register(monkeypatch)
    result = {
        "scope": "read_only",
        "status": "BLOCKED",
        "rows_checked": 141,
        "continuity_break_count": 12,
        "arithmetic_error_count": 0,
        "malformed_global_rows": 0,
        "current_wallet_credits": 30.072775,
        "ledger_tail_after": 30.072775,
        "current_balance_matches_tail": True,
        "findings": [{
            "type": "POSSIBLE_MIXED_DOMAIN_BOUNDARY",
            "previous": {"index": 116, "reason": "exchange:sell_reserve",
                         "domain_hint": "SLH_HINT", "after": 21549990.0},
            "next": {"index": 117, "reason": "store:purchase",
                     "domain_hint": "CREDITS_HINT", "before": 21992723.9},
            "delta_to_explain": 442733.9,
            "source_evidence_required": True,
        }],
        "findings_truncated": True,
        "blockers": ["ACCOUNT_LEDGER_SEQUENCE_DISCONTINUITY"],
    }
    with patch("state_manager.load_db", return_value={"ledger": []}), patch(
        "core.account_ledger_audit.audit_account_ledger", return_value=result
    ) as audit:
        bot.handlers["check_owner_ledger"](_message())

    audit.assert_called_once()
    output = bot.replies[-1]
    assert "OWNER ACCOUNT LEDGER — READ ONLY" in output
    assert "Continuity breaks: 12" in output
    assert "Row arithmetic errors: 0" in output
    assert "POSSIBLE_MIXED_DOMAIN_BOUNDARY" in output
    assert "source evidence required" in output
    assert "No DB, ledger, Credits, wallets, or gates changed" in output


def test_non_owner_cannot_read_owner_ledger(monkeypatch):
    bot = _register(monkeypatch)
    with patch("core.account_ledger_audit.audit_account_ledger") as audit:
        bot.handlers["check_owner_ledger"](_message(uid="5010371391"))
    audit.assert_not_called()
    assert "OWNER ONLY" in bot.replies[-1]


def test_owner_ledger_command_rejects_non_private_chat(monkeypatch):
    bot = _register(monkeypatch)
    with patch("core.account_ledger_audit.audit_account_ledger") as audit:
        bot.handlers["check_owner_ledger"](_message(chat_type="group"))
    audit.assert_not_called()
    assert "שיחה פרטית" in bot.replies[-1]
