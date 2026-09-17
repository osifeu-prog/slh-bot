import unittest
from unittest.mock import patch

from core import wallet_binding
import handlers.legacy_wallet_handler as legacy_wallet_handler


class FakeBot:
    def __init__(self):
        self.handlers = {}
        self.sent = []

    def message_handler(self, commands=None):
        def decorator(fn):
            for command in commands or []:
                self.handlers[command] = fn
            return fn
        return decorator

    def reply_to(self, msg, text, **kwargs):
        self.sent.append(text)


class Msg:
    def __init__(self, text):
        self.text = text
        self.from_user = type("User", (), {"id": 100})()


class LegacyWalletHandlerTests(unittest.TestCase):
    def test_migrate_without_address_explains_usage(self):
        bot = FakeBot()
        legacy_wallet_handler.register(bot)

        bot.handlers["migrate"](Msg("/migrate"))

        self.assertIn("/migrate <legacy_bnb_wallet>", bot.sent[-1])

    def test_migrate_issues_existing_wallet_challenge(self):
        bot = FakeBot()
        legacy_wallet_handler.register(bot)
        with patch.object(
            wallet_binding,
            "issue_challenge",
            return_value={"message": "SIGN ME", "expires_at": "x"},
        ):
            bot.handlers["migrate"](
                Msg("/migrate 0x0000000000000000000000000000000000000ABC")
            )

        self.assertIn("SIGN ME", bot.sent[-1])

    def test_verify_records_the_wallet_as_legacy_migrated(self):
        bot = FakeBot()
        legacy_wallet_handler.register(bot)
        with patch.object(
            wallet_binding,
            "verify_signature",
            return_value={"uid": "100", "address": "0x0000000000000000000000000000000000000ABC"},
        ), patch.object(
            legacy_wallet_handler,
            "record_legacy_claim",
            return_value={"status": "claimed"},
        ) as record:
            bot.handlers["migrate_verify"](
                Msg(
                    "/migrate_verify "
                    "0x0000000000000000000000000000000000000ABC "
                    "0x" + "11" * 65
                )
            )

        record.assert_called_once_with(
            "100",
            "0x0000000000000000000000000000000000000ABC",
            0,
        )
        self.assertIn("ארנק SLH הישן חובר", bot.sent[-1])


if __name__ == "__main__":
    unittest.main()
