from types import SimpleNamespace
from unittest.mock import patch

from handlers import system_checks_handler


OWNER_UID = 8789977826
OTHER_UID = 424242
TX = "0x" + "ab" * 32


class _Bot:
    def __init__(self):
        self.commands = {}
        self.replies = []

    def message_handler(self, *, commands):
        def decorate(fn):
            for command in commands:
                self.commands[command] = fn
            return fn
        return decorate

    def reply_to(self, message, text, **kwargs):
        self.replies.append((message, str(text)))


def _message(uid, text):
    return SimpleNamespace(from_user=SimpleNamespace(id=uid), text=text)


def test_existing_bnb_reconciliation_is_owner_only_and_gate_stays_closed():
    bot = _Bot()
    system_checks_handler.register(bot)
    handler = bot.commands.get("bnb_reconcile_existing")
    assert handler is not None, "owner BNB reconciliation command must be registered"

    denied = _message(OTHER_UID, f"/bnb_reconcile_existing {TX}")
    with patch("handlers.system_checks_handler.is_owner", return_value=False), patch(
        "core.bnb_empirical_smoke.reconcile_existing_settlement"
    ) as reconcile:
        handler(denied)
    assert "OWNER" in bot.replies[-1][1].upper()
    reconcile.assert_not_called()

    allowed = _message(OWNER_UID, f"/bnb_reconcile_existing {TX}")
    with patch("handlers.system_checks_handler.is_owner", return_value=True), patch(
        "core.bnb_empirical_smoke.reconcile_existing_settlement",
        return_value={
            "status": "PASS",
            "tx_hash": TX,
            "credits": 10.0,
            "gate_remained_closed": True,
        },
    ) as reconcile:
        handler(allowed)

    reconcile.assert_called_once_with(str(OWNER_UID), TX)
    reply = bot.replies[-1][1]
    assert "PASS" in reply
    assert "CLOSED" in reply.upper()
    assert "לא נשלחה" in reply
