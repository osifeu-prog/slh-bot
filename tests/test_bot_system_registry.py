import unittest
from unittest.mock import patch

from core import bot_system_registry


class BotSystemRegistryTests(unittest.TestCase):
    def setUp(self):
        self.db = {
            "users": {"1": {}},
            "bots": {
                "BOT_1": {
                    "id": "BOT_1",
                    "name": "Main",
                    "telegram_username": "@Me_ad_main_bot",
                    "role": "control_plane",
                    "template": "generic",
                    "status": "online",
                    "health": "HEALTHY",
                    "telemetry_status": "VERIFIED",
                    "lifecycle": "ACTIVE",
                    "last_heartbeat_at": "2026-09-27T12:00:00+00:00",
                    "last_heartbeat_status": "ok",
                }
            },
            "bot_vault": {
                "Me_ad_main_bot": {
                    "username": "Me_ad_main_bot",
                    "token_enc": "FERNET_CIPHERTEXT",
                    "token_tail": "…1234",
                    "module": "home",
                    "role": "control_plane",
                    "updated_at": "2026-09-27T12:00:00+00:00",
                    "exposures": [{"source": "chat", "at": "2026-09-27T11:00:00+00:00"}],
                }
            },
        }

    def test_snapshot_merges_runtime_vault_and_railway_metadata(self):
        with patch.object(bot_system_registry.state_manager, "load_db", return_value=self.db),              patch.object(bot_system_registry.bot_registry, "list_bots", return_value=[
                 self.db["bots"]["BOT_1"]
             ]), patch("core.bnb_gate.bnb_deposits_open", return_value=False),              patch("core.ton_deposit_service.deposits_are_open", return_value=False):
            data = bot_system_registry.snapshot()

        main = next(row for row in data["bots"] if row["username"] == "@Me_ad_main_bot")
        self.assertEqual(main["factory"]["health"], "HEALTHY")
        self.assertEqual(main["vault"]["token_tail"], "…1234")
        self.assertTrue(main["vault"]["encrypted"])
        self.assertEqual(len(main["railway_targets"]), 1)
        self.assertFalse(data["security"]["raw_tokens_in_read_model"])
        self.assertFalse(data["security"]["vault_decryption_performed"])
        self.assertNotIn("FERNET_CIPHERTEXT", repr(data))
        self.assertEqual(data["finance"]["bnb"]["gate"], "CLOSED")
        self.assertEqual(data["finance"]["ton"]["gate"], "CLOSED")

    def test_report_is_bounded_and_redacts_token_value(self):
        with patch.object(bot_system_registry.state_manager, "load_db", return_value=self.db),              patch.object(bot_system_registry.bot_registry, "list_bots", return_value=[]),              patch("core.bnb_gate.bnb_deposits_open", return_value=False),              patch("core.ton_deposit_service.deposits_are_open", return_value=False):
            out = bot_system_registry.report()

        self.assertLessEqual(len(out), 3800)
        self.assertNotIn("FERNET_CIPHERTEXT", out)
        self.assertIn("@Me_ad_main_bot", out)
        self.assertIn("BNB gate: CLOSED", out)
        self.assertIn("TON gate: CLOSED", out)


if __name__ == "__main__":
    unittest.main()
