import json
import os
import unittest
from unittest import mock

from cryptography.fernet import Fernet
from core import bot_vault

TOKEN = "123456789:AAaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
TOKEN2 = "123456789:BBbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
OTHER = "987654321:CCccccccccccccccccccccccccccccccccc"


def fake_get(url, timeout=15):
    response = mock.Mock()
    if url.endswith("/getMe"):
        bot_id = url.split("/bot", 1)[1].split(":", 1)[0]
        response.json.return_value = {
            "ok": True,
            "result": {"id": int(bot_id), "username": f"bot{bot_id}", "first_name": "B"},
        }
    else:
        response.json.return_value = {"ok": True, "result": {"url": "", "pending_update_count": 0}}
    return response


class BotVaultTests(unittest.TestCase):
    def setUp(self):
        self.db = {}
        self.env = mock.patch.dict(os.environ, {"SLH_VAULT_KEY": Fernet.generate_key().decode()})
        self.env.start()
        self.addCleanup(self.env.stop)

        patches = [
            mock.patch("state_manager.atomic_update", side_effect=lambda fn: fn(self.db)),
            mock.patch("state_manager.load_db", side_effect=lambda: self.db),
            mock.patch("core.bot_vault.requests.get", side_effect=fake_get),
        ]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_token_is_encrypted_and_never_in_audit(self):
        bot_vault.add_bot(TOKEN, actor="owner", module="academy")
        raw = json.dumps(self.db)
        self.assertNotIn(TOKEN, raw)
        self.assertEqual(bot_vault.get_token("bot123456789"), TOKEN)
        self.assertTrue(all(TOKEN not in json.dumps(a) for a in self.db["bot_vault_audit"]))

    def test_rotation_requires_same_bot(self):
        bot_vault.add_bot(TOKEN, actor="owner")
        with self.assertRaises(ValueError):
            bot_vault.rotate_bot("bot123456789", OTHER, actor="owner")
        bot_vault.rotate_bot("bot123456789", TOKEN2, actor="owner")
        self.assertEqual(bot_vault.get_token("bot123456789"), TOKEN2)

    def test_exposure_is_recommendation_not_block(self):
        bot_vault.add_bot(TOKEN, actor="owner")
        bot_vault.mark_exposed("bot123456789", "chat", actor="owner")
        self.assertEqual(bot_vault.list_bots()[0]["open_exposures"], 1)
        self.assertEqual(bot_vault.get_token("bot123456789"), TOKEN)
        bot_vault.rotate_bot("bot123456789", TOKEN2, actor="owner")
        self.assertEqual(bot_vault.list_bots()[0]["open_exposures"], 0)

    def test_missing_key_refuses_to_store(self):
        with mock.patch.dict(os.environ, {"SLH_VAULT_KEY": ""}):
            with self.assertRaises(ValueError):
                bot_vault.add_bot(TOKEN, actor="owner")

    def test_audit_distinguishes_add_and_update(self):
        bot_vault.add_bot(TOKEN, actor="owner")
        bot_vault.add_bot(TOKEN, actor="owner", module="wallet")
        self.assertEqual([a["action"] for a in self.db["bot_vault_audit"]], ["add", "update"])

    def test_remove_keeps_audit(self):
        bot_vault.add_bot(TOKEN, actor="owner")
        bot_vault.remove_bot("bot123456789", actor="owner")
        self.assertEqual(bot_vault.list_bots(), [])
        self.assertEqual(self.db["bot_vault_audit"][-1]["action"], "remove")


if __name__ == "__main__":
    unittest.main()
