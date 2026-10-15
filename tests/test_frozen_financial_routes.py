import copy
from types import SimpleNamespace
from unittest.mock import patch

from core import staking_service
from handlers import ui_exchange_handler


class FakeBot:
    def __init__(self):
        self.handlers = {}
        self.replies = []

    def message_handler(self, commands=None, **_kwargs):
        def decorate(function):
            for command in commands or []:
                self.handlers[command] = function
            return function
        return decorate

    def reply_to(self, _message, text, **_kwargs):
        self.replies.append(str(text))


def test_frozen_sender_cannot_use_p2p_credits_alternate_route():
    db = {
        "users": {
            "frozen-sender": {
                "frozen": True,
                "wallet": {"credits": 100.0},
            },
            "recipient": {"wallet": {"credits": 5.0}},
        },
        "ledger": [],
    }
    before = copy.deepcopy(db)
    bot = FakeBot()
    ui_exchange_handler.register(bot)
    message = SimpleNamespace(
        text="/p2p_credits recipient 10",
        from_user=SimpleNamespace(id="frozen-sender"),
        chat=SimpleNamespace(id=7),
        message_id=123,
    )

    with patch.object(
        ui_exchange_handler.state_manager,
        "atomic_update",
        side_effect=lambda mutate: mutate(db),
    ):
        bot.handlers["p2p_credits"](message)

    assert db == before
    assert bot.replies
    assert "ACCOUNT_FROZEN" in bot.replies[-1]


def test_frozen_account_cannot_move_credits_into_staking():
    db = {
        "users": {
            "frozen-user": {
                "frozen": True,
                "wallet": {"credits": 100.0, "staked": 0.0},
            }
        },
        "ledger": [],
    }
    before = copy.deepcopy(db)

    with patch.object(
        staking_service.state_manager,
        "atomic_update",
        side_effect=lambda mutate: mutate(db),
    ):
        try:
            staking_service.stake_locked(
                "frozen-user", 10, lock_days=30, request_id="frozen-stake-test",
            )
        except ValueError as exc:
            assert str(exc) == "ACCOUNT_FROZEN"
        else:
            raise AssertionError("Expected ACCOUNT_FROZEN")

    assert db == before
