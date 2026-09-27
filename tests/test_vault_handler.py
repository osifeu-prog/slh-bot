import os
import unittest
from types import SimpleNamespace
from unittest import mock

from cryptography.fernet import Fernet

TOKEN = "123456789:AAaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


class FakeBot:
    def __init__(self):
        self.handlers = {}
        self.sent = []
        self.deleted = []

    def message_handler(self, commands=None, **_):
        def deco(fn):
            for c in commands or []:
                self.handlers[c] = fn
            return fn
        return deco

    def reply_to(self, msg, text):
        self.sent.append(text)

    def send_message(self, chat_id, text):
        self.sent.append(text)

    def delete_message(self, chat_id, mid):
        self.deleted.append(mid)


def msg(text, uid=1, chat="private"):
    return SimpleNamespace(
        text=text,
        message_id=7,
        chat=SimpleNamespace(id=uid, type=chat),
        from_user=SimpleNamespace(id=uid),
    )


class VaultHandlerTests(unittest.TestCase):
    def setUp(self):
        self.db = {}
        env = mock.patch.dict(os.environ, {"SLH_VAULT_KEY": Fernet.generate_key().decode(), "OWNER_ID": "1"})
        env.start()
        self.addCleanup(env.stop)

        patches = [
            mock.patch("state_manager.atomic_update", side_effect=lambda fn: fn(self.db)),
            mock.patch("state_manager.load_db", side_effect=lambda: self.db),
            mock.patch("core.bot_vault.requests.get", return_value=mock.Mock()),
            mock.patch("core.authority.get_role", return_value="OWNER"),
        ]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)

        from handlers import vault_handler
        self.bot = FakeBot()
        vault_handler.register(self.bot)

    def test_non_private_chat_ignored(self):
        self.bot.handlers["vault_add"](msg(f"/vault_add {TOKEN}", chat="group"))
        self.assertEqual(self.db, {})

    def test_non_owner_denied(self):
        with mock.patch("core.authority.get_role", return_value="USER"):
            self.bot.handlers["vault"](msg("/vault", uid=2))
        self.assertIn("לבעלים בלבד", self.bot.sent[-1])

    def test_add_deletes_token_message(self):
        self.bot.handlers["vault_add"](msg(f"/vault_add {TOKEN} academy"))
        self.assertIn(7, self.bot.deleted)
        self.assertTrue(all(TOKEN not in s for s in self.bot.sent))


if __name__ == "__main__":
    unittest.main()
