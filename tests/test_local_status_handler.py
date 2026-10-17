import unittest
from types import SimpleNamespace
from unittest.mock import patch

from handlers import local_status_handler


class FakeBot:
    def __init__(self):
        self.handlers = {}
        self.sent = []

    def message_handler(self, commands=None, **_kwargs):
        def decorator(fn):
            for command in commands or []:
                self.handlers[command] = fn
            return fn
        return decorator

    def reply_to(self, message, text):
        self.sent.append(text)


def message(uid=8789977826, chat_type="private"):
    return SimpleNamespace(
        from_user=SimpleNamespace(id=uid),
        chat=SimpleNamespace(type=chat_type),
        text="/local_status",
    )


class LocalStatusHandlerTests(unittest.TestCase):
    def setUp(self):
        self.bot = FakeBot()
        local_status_handler.register(self.bot)

    def test_non_owner_is_denied(self):
        with patch.object(local_status_handler, "is_owner", return_value=False):
            self.bot.handlers["local_status"](message(uid=123))
        self.assertIn("Owner only", self.bot.sent[-1])

    def test_group_chat_is_denied(self):
        with patch.object(local_status_handler, "is_owner", return_value=True):
            self.bot.handlers["local_status"](message(chat_type="group"))
        self.assertIn("private chat", self.bot.sent[-1])

    def test_reports_presence_and_explicitly_disclaims_missing_diagnostics(self):
        reports = [
            {"status": "online", "age_seconds": 12, "records": 1},
            {"status": "offline", "age_seconds": 320, "records": 1},
        ]
        with patch.object(local_status_handler, "is_owner", return_value=True), \
             patch.object(local_status_handler, "get_device_status", side_effect=reports) as read:
            self.bot.handlers["local_status"](message())

        output = self.bot.sent[-1]
        self.assertIn("PC_Osif2: ONLINE", output)
        self.assertIn("PC_MAIN_001: OFFLINE", output)
        self.assertIn("Docker / Git / container logs: NOT REPORTED", output)
        self.assertIn("No commands were executed", output)
        self.assertEqual(read.call_count, 2)

    def test_read_failure_is_fail_closed_without_traceback(self):
        with patch.object(local_status_handler, "is_owner", return_value=True), \
             patch.object(local_status_handler, "get_device_status", side_effect=RuntimeError("secret/token")):
            self.bot.handlers["local_status"](message())

        output = self.bot.sent[-1]
        self.assertIn("status read failed", output)
        self.assertNotIn("secret/token", output)


if __name__ == "__main__":
    unittest.main()
