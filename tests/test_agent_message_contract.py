import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core import agent_registry
from handlers import agents_handler


class FakeBot:
    def __init__(self):
        self.handlers = {}
        self.replies = []

    def message_handler(self, commands=None, **_kwargs):
        def decorate(function):
            for command in commands or []:
                self.handlers[str(command).lstrip("/")] = function
            return function
        return decorate

    def reply_to(self, _message, text, **_kwargs):
        self.replies.append(str(text))


def _message(text):
    return SimpleNamespace(
        text=text,
        from_user=SimpleNamespace(id=8789977826),
        chat=SimpleNamespace(id=12345),
        message_id=678,
    )


class AgentMessageContractTests(unittest.TestCase):
    def test_send_message_preserves_structured_ask_and_deduplicates_pending_request(self):
        db = {"users": {"owner": {}}, "agents": {"16": {"name": "helper", "inbox": [], "outbox": []}}}
        payload = {
            "command": "ask",
            "prompt": "Check the system status",
            "uid": "owner",
            "request_id": "telegram:owner:chat:message",
        }

        with (
            patch.object(agent_registry, "get_agent", return_value=("16", {"name": "helper"})),
            patch.object(
                agent_registry.state_manager,
                "atomic_update",
                side_effect=lambda mutate: mutate(db),
            ),
            patch.object(agent_registry.STORE, "rebuild_snapshot"),
            patch.object(agent_registry, "log_event"),
        ):
            agent_registry.send_message("helper", payload)
            agent_registry.send_message("helper", payload)

        self.assertEqual(db["agents"]["16"]["inbox"], [payload])

    def test_legacy_string_messages_remain_compatible(self):
        db = {"users": {"owner": {}}, "agents": {"16": {"name": "helper", "inbox": [], "outbox": []}}}
        with (
            patch.object(agent_registry, "get_agent", return_value=("16", {"name": "helper"})),
            patch.object(
                agent_registry.state_manager,
                "atomic_update",
                side_effect=lambda mutate: mutate(db),
            ),
            patch.object(agent_registry.STORE, "rebuild_snapshot"),
            patch.object(agent_registry, "log_event"),
        ):
            agent_registry.send_message("helper", "legacy message")

        self.assertEqual(db["agents"]["16"]["inbox"], ["legacy message"])

    def test_sendagent_queues_prompt_as_ask_instead_of_echoing_raw_command(self):
        bot = FakeBot()
        agents_handler.register(bot, None)
        agent = {"name": "helper"}
        with (
            patch.object(agents_handler, "_check_access", return_value=("16", agent)),
            patch.object(agents_handler, "send_message") as send_message,
        ):
            bot.handlers["sendagent"](_message("/sendagent helper ask בדוק התקדמות"))

        send_message.assert_called_once()
        agent_id, payload = send_message.call_args.args
        self.assertEqual(agent_id, "16")
        self.assertEqual(payload["command"], "ask")
        self.assertEqual(payload["prompt"], "בדוק התקדמות")
        self.assertEqual(payload["uid"], "8789977826")
        self.assertEqual(payload["request_id"], "telegram:8789977826:12345:678")
        self.assertIn("/agent_outbox 16", bot.replies[-1])

    def test_inbox_reads_the_actual_inbox_list_from_tuple_contract(self):
        bot = FakeBot()
        agents_handler.register(bot, None)
        with (
            patch.object(agents_handler, "_check_access", return_value=("16", {"name": "helper"})),
            patch.object(agents_handler, "get_inbox", return_value=("16", [{"command": "ask"}])),
        ):
            bot.handlers["inbox"](_message("/inbox helper"))

        self.assertIn("command", bot.replies[-1])
        self.assertNotIn("empty", bot.replies[-1])

    def test_agent_outbox_returns_recent_results_to_authorized_caller(self):
        bot = FakeBot()
        agents_handler.register(bot, None)
        with (
            patch.object(agents_handler, "_check_access", return_value=("16", {"name": "helper"})),
            patch.object(agents_handler, "get_outbox", return_value=("16", ["older result", "newer result"])),
        ):
            bot.handlers["agent_outbox"](_message("/agent_outbox helper"))

        self.assertIn("newest first", bot.replies[-1])
        self.assertLess(bot.replies[-1].index("newer result"), bot.replies[-1].index("older result"))

    def test_worker_ask_uses_canonical_slh_ai_router(self):
        from internal_agent import run_command

        with patch("core.ask_router.route", return_value="answer from configured fallback chain") as route:
            result = run_command(
                "ask",
                {"prompt": "Explain the current architecture", "uid": "8789977826"},
            )

        self.assertEqual(result, "answer from configured fallback chain")
        route.assert_called_once_with("Explain the current architecture", uid="8789977826")


if __name__ == "__main__":
    unittest.main()
