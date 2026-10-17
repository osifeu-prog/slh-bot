import unittest
from types import SimpleNamespace
from unittest.mock import patch

from handlers import agents_handler


class FakeBot:
    def __init__(self):
        self.handlers = {}
        self.replies = []

    def message_handler(self, commands=None, **_kwargs):
        def decorate(fn):
            for command in commands or []:
                self.handlers[str(command)] = fn
            return fn
        return decorate

    def reply_to(self, _message, text, **_kwargs):
        self.replies.append(str(text))


class AgentHandlerTaskTests(unittest.TestCase):
    def setUp(self):
        self.bot = FakeBot()
        agents_handler.register(self.bot, None)
        self.agent = {
            "id": "16",
            "name": "Alpha",
            "owner_id": "123",
            "outbox": [],
        }

    def _message(self, text):
        return SimpleNamespace(
            text=text,
            from_user=SimpleNamespace(id=123),
        )

    def test_sendagent_queues_free_text_as_an_ask_task(self):
        msg = self._message("/sendagent Alpha check progress and report ledger")
        with (
            patch("handlers.agents_handler.normalize_uid", return_value="123"),
            patch("handlers.agents_handler._check_access", return_value=("16", self.agent)),
            patch("handlers.agents_handler.is_owner", return_value=False),
            patch("handlers.agents_handler.send_message") as send,
        ):
            self.bot.handlers["sendagent"](msg)

        send.assert_called_once_with(
            "16",
            {
                "command": "ask",
                "prompt": "check progress and report ledger",
                "uid": "123",
            },
        )
        self.assertIn("/agentoutbox Alpha", self.bot.replies[-1])

    def test_non_owner_cannot_turn_plain_text_restart_into_a_restart_command(self):
        msg = self._message("/sendagent Alpha restart")
        with (
            patch("handlers.agents_handler.normalize_uid", return_value="123"),
            patch("handlers.agents_handler._check_access", return_value=("16", self.agent)),
            patch("handlers.agents_handler.is_owner", return_value=False),
            patch("handlers.agents_handler.send_message") as send,
        ):
            self.bot.handlers["sendagent"](msg)

        task = send.call_args.args[1]
        self.assertEqual(task["command"], "ask")
        self.assertEqual(task["prompt"], "restart")

    def test_restart_text_is_not_routed_to_the_legacy_restart_command_even_for_owner(self):
        msg = self._message("/sendagent Alpha restart")
        with (
            patch("handlers.agents_handler.normalize_uid", return_value="123"),
            patch("handlers.agents_handler._check_access", return_value=("16", self.agent)),
            patch("handlers.agents_handler.is_owner", return_value=True),
            patch("handlers.agents_handler.send_message") as send,
        ):
            self.bot.handlers["sendagent"](msg)

        task = send.call_args.args[1]
        self.assertEqual(task["command"], "ask")
        self.assertEqual(task["prompt"], "restart")

    def test_agentoutbox_displays_only_the_authorized_agents_recent_results(self):
        self.agent["outbox"] = ["first", "second"]
        msg = self._message("/agentoutbox Alpha")
        with (
            patch("handlers.agents_handler.normalize_uid", return_value="123"),
            patch("handlers.agents_handler._check_access", return_value=("16", self.agent)),
        ):
            self.bot.handlers["agentoutbox"](msg)

        self.assertIn("first", self.bot.replies[-1])
        self.assertIn("second", self.bot.replies[-1])


if __name__ == "__main__":
    unittest.main()
