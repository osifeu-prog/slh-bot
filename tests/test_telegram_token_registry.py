import unittest

from core.telegram_token_registry import get_bot, list_bots, targets_for


class TelegramTokenRegistryTests(unittest.TestCase):
    def test_known_bot_registry_is_non_secret_and_complete(self):
        bots = {b["alias"]: b for b in list_bots()}
        self.assertTrue({"main", "air", "claude", "ton"}.issubset(bots))
        self.assertEqual(bots["main"]["username"], "Me_ad_main_bot")
        self.assertEqual(bots["air"]["username"], "SLH_AIR_bot")
        self.assertEqual(bots["claude"]["username"], "SLH_Claude_bot")
        self.assertEqual(bots["ton"]["username"], "TON_MNH_bot")
        self.assertNotIn("AAG", repr(bots))
        self.assertNotIn("1234567890:", repr(bots))

    def test_air_uses_dedicated_telegram_token_variable(self):
        targets = targets_for("air")
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0]["variable"], "TELEGRAM_TOKEN")
        self.assertEqual(targets[0]["service"], "slh-air-bot")

    def test_claude_uses_dedicated_token_variable(self):
        targets = targets_for("claude")
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0]["variable"], "SLH_CLAUDE_BOT_TOKEN")
        self.assertEqual(targets[0]["service"], "slh-AI-bot")

    def test_ton_updates_webhook_and_worker(self):
        targets = targets_for("ton")
        self.assertEqual(len(targets), 2)
        self.assertEqual(
            {t["service"] for t in targets},
            {"SLH_PROJECT_V2", "glorious-caring"},
        )
        self.assertEqual({t["variable"] for t in targets}, {"BOT_TOKEN"})

    def test_unknown_alias_fails_closed(self):
        with self.assertRaises(KeyError):
            get_bot("not-a-real-bot")

    def test_control_surface_never_contains_token_value(self):
        from refresh_token_handler import bots_text, rotation_instructions

        text = bots_text() + "\n" + rotation_instructions("air")
        self.assertNotIn("TELEGRAM_TOKEN=", text)
        self.assertNotIn("SLH_CLAUDE_BOT_TOKEN=", text)
        self.assertNotIn("New Telegram token", text)
        self.assertIn("Run this from the operator terminal", text)
        self.assertIn("rotate_telegram_token.sh air", text)

    def test_rotation_instructions_fail_closed_for_unknown_alias(self):
        from refresh_token_handler import rotation_instructions

        with self.assertRaises(KeyError):
            rotation_instructions("wrong")


if __name__ == "__main__":
    unittest.main()
