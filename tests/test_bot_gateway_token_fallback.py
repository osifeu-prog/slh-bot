import os
import unittest
from unittest.mock import patch

import bot_gateway


class PrimaryTelegramTokenFallbackTests(unittest.TestCase):
    def test_environment_token_is_first_candidate(self):
        with patch.dict(os.environ, {"BOT_TOKEN": "env-token"}), patch(
            "core.bot_vault.get_token", return_value="vault-token"
        ):
            candidates = bot_gateway.primary_bot_token_candidates()
        self.assertEqual(candidates, [
            ("environment", "env-token"),
            ("bot_vault", "vault-token"),
        ])

    def test_duplicate_vault_token_is_not_added(self):
        with patch.dict(os.environ, {"BOT_TOKEN": "same-token"}), patch(
            "core.bot_vault.get_token", return_value="same-token"
        ):
            candidates = bot_gateway.primary_bot_token_candidates()
        self.assertEqual(candidates, [("environment", "same-token")])

    def test_missing_environment_token_uses_vault(self):
        with patch.dict(os.environ, {"BOT_TOKEN": ""}), patch(
            "core.bot_vault.get_token", return_value="vault-token"
        ):
            candidates = bot_gateway.primary_bot_token_candidates()
        self.assertEqual(candidates, [("bot_vault", "vault-token")])

    def test_vault_failure_does_not_break_environment_token(self):
        with patch.dict(os.environ, {"BOT_TOKEN": "env-token"}), patch(
            "core.bot_vault.get_token", side_effect=ValueError("BOT_NOT_IN_VAULT")
        ):
            candidates = bot_gateway.primary_bot_token_candidates()
        self.assertEqual(candidates, [("environment", "env-token")])


if __name__ == "__main__":
    unittest.main()
