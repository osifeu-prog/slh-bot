import unittest
from pathlib import Path


class VaultWebAppSecurityTest(unittest.TestCase):
    def test_api_is_owner_only_and_does_not_return_decrypted_tokens(self):
        src = Path("webapp.py").read_text(encoding="utf-8")
        self.assertIn('@app.route("/api/v1/vault")', src)
        self.assertIn('get_role(normalize_uid(uid)) != "OWNER"', src)
        self.assertIn('"bots": bot_vault.list_bots()', src)
        self.assertNotIn('get_token(', src[src.index('@app.route("/api/v1/vault")'):src.index('@app.route("/api/v1/me")')])

    def test_ui_does_not_contain_token_input(self):
        src = Path("mini_app.html").read_text(encoding="utf-8")
        self.assertIn('<section id="vault" class="screen">', src)
        self.assertIn('Owner-only Bot Vault', src)
        self.assertNotIn('id="vaultToken"', src)
        self.assertNotIn('name="vaultToken"', src)


if __name__ == "__main__":
    unittest.main()
