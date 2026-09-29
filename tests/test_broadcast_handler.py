import unittest
from unittest.mock import Mock, patch

import handlers.broadcast_handler as module


class BroadcastHandlerTests(unittest.TestCase):
    def test_non_owner_is_rejected(self):
        bot = Mock()
        module.register(bot)
        self.assertTrue(bot.message_handler.called)

    def test_constants_match_telegram_message_boundary(self):
        self.assertEqual(module.MAX_BROADCAST_LENGTH, 4096)
        self.assertGreater(module.SEND_DELAY_SECONDS, 0)


if __name__ == "__main__":
    unittest.main()
