from types import SimpleNamespace
from unittest.mock import patch

from core import command_catalog
from handlers import help_handler
from handlers.llm_handler import AI_FACTUALITY_POLICY, SLH_SYSTEM_RULES


class FakeBot:
    def __init__(self):
        self.handlers = {}
        self.replies = []

    def message_handler(self, commands):
        def register(fn):
            for command in commands:
                self.handlers[command] = fn
            return fn
        return register

    def reply_to(self, message, text, **kwargs):
        self.replies.append((message, text))


def _message(uid, text):
    return SimpleNamespace(
        from_user=SimpleNamespace(id=uid),
        text=text,
        chat=SimpleNamespace(id=uid),
    )


def test_public_help_only_shows_runtime_verified_allowlisted_commands():
    runtime = [
        "start", "help", "academy", "ask", "trade_model",
        "e", "deploy", "redeploy", "bnb_reverse_confirm",
        "bnb_reconcile_confirm", "alpha_open", "mystery_runtime_command",
    ]
    with patch.object(command_catalog, "_runtime_commands", return_value=runtime):
        rendered = command_catalog.render_public_help("Me_ad_main")

    assert "/start — " in rendered
    assert "/ask — " in rendered
    assert "/trade_model — " in rendered
    for private_command in (
        "/e", "/deploy", "/redeploy", "/bnb_reverse_confirm",
        "/bnb_reconcile_confirm", "/alpha_open", "/mystery_runtime_command",
    ):
        assert private_command not in rendered


def test_closed_exchange_never_displays_ready_to_open_as_permission():
    result = {
        "public_gate": "CLOSED",
        "public_ready": True,
        "verdict": "READY_TO_OPEN",
        "ok": True,
    }
    with patch("core.system_checks.check_exchange", return_value=result):
        rendered = help_handler._exchange_status_line()

    assert "CLOSED" in rendered
    assert "diagnostic only" in rendered
    assert "trading remains closed" in rendered
    assert "READY_TO_OPEN" not in rendered


def test_exchange_status_is_not_shown_as_open_without_all_check_results():
    result = {
        "public_gate": "OPEN",
        "public_ready": True,
        "verdict": "BLOCKED",
        "ok": False,
    }
    with patch("core.system_checks.check_exchange", return_value=result):
        rendered = help_handler._exchange_status_line()

    assert "status unverified" in rendered
    assert "blocked" in rendered


def test_gate_open_is_not_displayed_without_integrated_reserve_release_evidence():
    result = {
        "public_gate": "OPEN",
        "public_ready": True,
        "verdict": "OPEN",
        "ok": True,
    }
    with patch("core.system_checks.check_exchange", return_value=result):
        rendered = help_handler._exchange_status_line()

    assert "status unverified" in rendered
    assert "blocked" in rendered


def test_gate_open_requires_explicit_zero_blocker_reserve_release_pass():
    result = {
        "public_gate": "OPEN",
        "public_ready": True,
        "verdict": "OPEN",
        "ok": True,
        "reserve_reconciliation_ok": True,
        "reserve_blocking_count": 0,
    }
    with patch("core.system_checks.check_exchange", return_value=result):
        rendered = help_handler._exchange_status_line()

    assert "OPEN" in rendered
    assert "canonical readiness checks PASS" in rendered


def test_public_help_handler_uses_public_catalog_and_opshelp_is_owner_only():
    bot = FakeBot()
    help_handler.register(bot)
    msg = _message(12345, "/help")

    with (
        patch("handlers.help_handler._exchange_status_line", return_value="EXCHANGE CLOSED"),
        patch("core.command_catalog.render_public_help", return_value="PUBLIC CATALOG"),
    ):
        bot.handlers["help"](msg)

    assert "PUBLIC CATALOG" in bot.replies[-1][1]
    assert "/deploy" not in bot.replies[-1][1]

    with patch("handlers.help_handler.is_owner", return_value=False):
        bot.handlers["opshelp"](_message(12345, "/opshelp"))
    assert "בעלים בלבד" in bot.replies[-1][1]

    with (
        patch("handlers.help_handler.is_owner", return_value=True),
        patch("handlers.help_handler._exchange_status_line", return_value="EXCHANGE STATUS"),
        patch("core.command_catalog.render_help", return_value="PRIVATE OPERATIONS CATALOG"),
    ):
        bot.handlers["opshelp"](_message(8789977826, "/opshelp"))
    assert "PRIVATE OPERATIONS CATALOG" in bot.replies[-1][1]


def test_ai_grounding_policy_addresses_unverified_investor_numbers_and_legal_claims():
    assert "Never invent active-user counts" in AI_FACTUALITY_POLICY
    assert "as already approved or implemented" in AI_FACTUALITY_POLICY
    assert "non-custodial architecture eliminates legal/regulatory liability" in AI_FACTUALITY_POLICY
    assert "Only mention commands present in the runtime command registry" in AI_FACTUALITY_POLICY
    assert "Never invent user counts" in SLH_SYSTEM_RULES
    assert "Do not claim a gate is OPEN" in SLH_SYSTEM_RULES
