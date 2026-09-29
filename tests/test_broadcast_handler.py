import unittest
from unittest.mock import patch

from handlers.broadcast_handler import MAX_BROADCAST_CHARS, perform_broadcast


class _Bot:
    def __init__(self, failures=None):
        self.failures = set(failures or [])
        self.sent = []

    def send_message(self, uid, text):
        if uid in self.failures:
            raise RuntimeError("send failed")
        self.sent.append((uid, text))


class BroadcastTests(unittest.TestCase):
    def test_perform_broadcast_counts_successes_and_failures(self):
        bot = _Bot(failures={"2"})
        with patch("handlers.broadcast_handler.time.sleep"):
            result = perform_broadcast(bot, ["1", "2", "3"], "Hello")

        self.assertEqual(result, {"sent": 2, "failed": 1})
        self.assertEqual(bot.sent, [("1", "Hello"), ("3", "Hello")])

    def test_broadcast_character_limit_is_explicit(self):
        self.assertEqual(MAX_BROADCAST_CHARS, 4000)

    def test_perform_broadcast_handles_empty_recipient_set(self):
        bot = _Bot()
        with patch("handlers.broadcast_handler.time.sleep"):
            result = perform_broadcast(bot, [], "Hello")
        self.assertEqual(result, {"sent": 0, "failed": 0})


if __name__ == "__main__":
    unittest.main()
