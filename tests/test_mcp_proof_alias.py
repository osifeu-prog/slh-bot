import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from handlers import mcp_proof_handler


class _Bot:
    def __init__(self):
        self.handlers = {}
        self.replies = []

    def message_handler(self, *, commands):
        def register(fn):
            for command in commands:
                self.handlers[command] = fn
            return fn
        return register

    def reply_to(self, message, text):
        self.replies.append((message, text))


def _message(uid, command):
    return SimpleNamespace(
        from_user=SimpleNamespace(id=uid),
        text="/" + command,
    )


class MCPProofAliasTests(unittest.TestCase):
    def test_mcp_alias_and_mcp_test_use_the_same_owner_only_handler(self):
        bot = _Bot()
        mcp_proof_handler.register(bot)

        self.assertIn("mcp", bot.handlers)
        self.assertIn("mcp_test", bot.handlers)
        self.assertIs(bot.handlers["mcp"], bot.handlers["mcp_test"])

    def test_mcp_alias_rejects_non_owner_without_network_access(self):
        bot = _Bot()
        mcp_proof_handler.register(bot)
        message = _message(123, "mcp")

        with (
            patch.object(mcp_proof_handler, "is_owner", return_value=False),
            patch.object(mcp_proof_handler.requests, "get") as get,
        ):
            bot.handlers["mcp"](message)

        self.assertIn("Owner only", bot.replies[-1][1])
        get.assert_not_called()

    def test_mcp_alias_reuses_existing_read_only_proof_contract(self):
        bot = _Bot()
        mcp_proof_handler.register(bot)
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "status": "PASS",
            "runtime": {
                "state": "RUNNING",
                "running": True,
                "boot_ok": True,
                "agent_count": 3,
            },
        }

        with (
            patch.object(mcp_proof_handler, "is_owner", return_value=True),
            patch.dict(os.environ, {
                "SLH_MCP_URL": "https://mcp.example.invalid",
                "SLH_MCP_BRIDGE_TOKEN": "test-only-token",
            }),
            patch.object(mcp_proof_handler.requests, "get", return_value=response) as get,
        ):
            bot.handlers["mcp_test"](_message(8789977826, "mcp_test"))
            bot.handlers["mcp"](_message(8789977826, "mcp"))

        self.assertEqual(len(bot.replies), 2)
        self.assertEqual(bot.replies[0][1], bot.replies[1][1])
        self.assertIn("MCP TELEGRAM PROOF PASS", bot.replies[1][1])
        self.assertEqual(get.call_count, 2)
        self.assertTrue(all(call.kwargs.get("timeout") == 15 for call in get.call_args_list))


if __name__ == "__main__":
    unittest.main()
