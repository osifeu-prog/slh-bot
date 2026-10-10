import unittest
from types import SimpleNamespace
from unittest.mock import patch

from handlers import exchange_handler


class _FakeBot:
    def __init__(self):
        self.handlers = {}
        self.replies = []

    def message_handler(self, commands=None, **kwargs):
        def decorate(fn):
            for command in commands or []:
                self.handlers[command] = fn
            return fn
        return decorate

    def reply_to(self, message, text):
        self.replies.append(text)


def _message(text, uid=100, chat_type="private"):
    return SimpleNamespace(
        text=text,
        from_user=SimpleNamespace(id=uid),
        chat=SimpleNamespace(type=chat_type),
    )


class ExchangeGateTelegramCommandTests(unittest.TestCase):
    def setUp(self):
        self.bot = _FakeBot()
        exchange_handler.register(self.bot)
        self.command = self.bot.handlers["exchange_gate"]

    def test_close_is_owner_private_and_reports_deployment_not_false_success(self):
        result = {
            "status": "DEPLOY_TRIGGERED",
            "previous": "1",
            "configured": "0",
            "commit": "a" * 40,
            "deployment_id": "dep-123",
            "service": "slh-cloud-bot",
            "environment": "production",
        }
        with patch("handlers.exchange_handler.is_owner", return_value=True), \
             patch("core.exchange_gate_bridge.close_exchange_gate_via_mcp", return_value=result) as close:
            self.command(_message("/exchange_gate close"))

        close.assert_called_once_with()
        reply = self.bot.replies[-1]
        self.assertIn("SLH_EXCHANGE_PUBLIC_OPEN=0", reply)
        self.assertIn("dep-123", reply)
        self.assertIn("CLOSED VERIFIED", reply)
        self.assertIn("NOT marked complete", reply)

    def test_close_is_rejected_outside_private_chat(self):
        with patch("handlers.exchange_handler.is_owner", return_value=True), \
             patch("core.exchange_gate_bridge.close_exchange_gate_via_mcp") as close:
            self.command(_message("/exchange_gate close", chat_type="group"))

        close.assert_not_called()
        self.assertIn("רק בפרטי", self.bot.replies[-1])

    def test_non_owner_cannot_close(self):
        with patch("handlers.exchange_handler.is_owner", return_value=False), \
             patch("core.exchange_gate_bridge.close_exchange_gate_via_mcp") as close:
            self.command(_message("/exchange_gate close", uid=999))

        close.assert_not_called()
        self.assertIn("OWNER only", self.bot.replies[-1])

    def test_status_distinguishes_configured_value_from_live_runtime(self):
        closed_check = {
            "public_gate": "CLOSED",
            "execution_ready": False,
            "open_orders": 0,
        }
        with patch("handlers.exchange_handler.is_owner", return_value=True), \
             patch.dict("os.environ", {"SLH_EXCHANGE_PUBLIC_OPEN": "0"}, clear=False), \
             patch("core.exchange_gate_bridge.exchange_gate_status", return_value={"configured": "0"}), \
             patch("handlers.exchange_handler.state_manager.load_db", return_value={"users": {}}), \
             patch("core.system_checks.check_exchange_for_execution", return_value=closed_check):
            self.command(_message("/exchange_gate status"))

        reply = self.bot.replies[-1]
        self.assertIn("CLOSED VERIFIED", reply)
        self.assertIn("execution_ready: False", reply)


    def test_status_keeps_runtime_diagnostic_when_railway_api_token_is_missing(self):
        from core.exchange_gate_bridge import ExchangeGateBridgeError

        open_check = {
            "public_gate": "OPEN",
            "execution_ready": True,
            "open_orders": 0,
        }
        with patch("handlers.exchange_handler.is_owner", return_value=True), \
             patch.dict("os.environ", {"SLH_EXCHANGE_PUBLIC_OPEN": "1"}, clear=False), \
             patch("core.exchange_gate_bridge.exchange_gate_status", side_effect=ExchangeGateBridgeError("RAILWAY_CONTROL_TOKEN_MISSING")), \
             patch("handlers.exchange_handler.state_manager.load_db", return_value={"users": {}}), \
             patch("core.system_checks.check_exchange_for_execution", return_value=open_check):
            self.command(_message("/exchange_gate status"))

        reply = self.bot.replies[-1]
        self.assertIn("Railway Production variable: UNKNOWN", reply)
        self.assertIn("Runtime env: 1", reply)
        self.assertIn("Effective gate: OPEN", reply)
        self.assertIn("RAILWAY_CONTROL_TOKEN_MISSING", reply)
        self.assertIn("🔴 OPEN", reply)

if __name__ == "__main__":
    unittest.main()
