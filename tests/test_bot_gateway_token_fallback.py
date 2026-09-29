import os
import unittest
from unittest.mock import patch

import bot_gateway


class PrimaryTelegramTokenFallbackTests(unittest.TestCase):
    def test_environment_token_is_first_candidate(self):
        with patch.dict(
            os.environ,
            {"BOT_TOKEN": "env-token", "TOKEN_1": "token1", "TOKEN_2": "token2", "TOKEN_3": "token3"},
            clear=False,
        ), patch(
            "core.bot_vault.get_token_by_identity", return_value="vault-token"
        ):
            candidates = bot_gateway.primary_bot_token_candidates()
        self.assertEqual(
            candidates[:2],
            [("environment", "env-token"), ("bot_vault", "vault-token")],
        )
        self.assertEqual(
            candidates[2:],
            [("token_1", "token1"), ("token_2", "token2"), ("token_3", "token3")],
        )

    def test_duplicate_vault_token_is_not_added(self):
        with patch.dict(os.environ, {"BOT_TOKEN": "same-token", "TOKEN_1": ""}, clear=False), patch(
            "core.bot_vault.get_token_by_identity", return_value="same-token"
        ):
            candidates = bot_gateway.primary_bot_token_candidates()
        self.assertEqual(candidates[0], ("environment", "same-token"))
        self.assertNotIn(("bot_vault", "same-token"), candidates)

    def test_missing_environment_token_uses_vault(self):
        with patch.dict(os.environ, {"BOT_TOKEN": "", "TOKEN_1": "", "TOKEN_2": "", "TOKEN_3": ""}, clear=False), patch(
            "core.bot_vault.get_token_by_identity", return_value="vault-token"
        ):
            candidates = bot_gateway.primary_bot_token_candidates()
        self.assertEqual(candidates, [("bot_vault", "vault-token")])

    def test_alias_tokens_are_available_as_fallback_candidates(self):
        with patch.dict(
            os.environ,
            {"BOT_TOKEN": "", "TOKEN_1": "token1", "TOKEN_2": "token2", "TOKEN_3": "token3"},
            clear=False,
        ), patch(
            "core.bot_vault.get_token_by_identity", side_effect=ValueError("BOT_NOT_IN_VAULT")
        ):
            self.assertEqual(
                bot_gateway.primary_bot_token_candidates(),
                [("token_1", "token1"), ("token_2", "token2"), ("token_3", "token3")],
            )

    def test_vault_failure_does_not_break_environment_token(self):
        with patch.dict(os.environ, {"BOT_TOKEN": "env-token", "TOKEN_1": ""}, clear=False), patch(
            "core.bot_vault.get_token_by_identity", side_effect=ValueError("BOT_NOT_IN_VAULT")
        ):
            candidates = bot_gateway.primary_bot_token_candidates()
        self.assertEqual(candidates[0], ("environment", "env-token"))


if __name__ == "__main__":
    unittest.main()
