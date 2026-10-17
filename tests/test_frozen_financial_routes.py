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


def _message(sender="frozen-sender", recipient="recipient", amount=10, chat_id=7, message_id=123):
    return SimpleNamespace(
        text=f"/p2p_credits {recipient} {amount}",
        from_user=SimpleNamespace(id=sender),
        chat=SimpleNamespace(id=chat_id),
        message_id=message_id,
    )


def test_frozen_sender_cannot_use_p2p_credits_alternate_route():
    db = {
        "users": {
            "frozen-sender": {"frozen": True, "wallet": {"credits": 100.0}},
            "recipient": {"wallet": {"credits": 5.0}},
        },
        "ledger": [],
    }
    before = copy.deepcopy(db)
    bot = FakeBot()
    ui_exchange_handler.register(bot)

    with patch.object(
        ui_exchange_handler.state_manager,
        "atomic_update",
        side_effect=lambda mutate: mutate(db),
    ):
        bot.handlers["p2p_credits"](_message())

    assert db == before
    assert bot.replies
    assert "ACCOUNT_FROZEN" in bot.replies[-1]


def test_frozen_sender_can_replay_exact_completed_p2p_message_without_mutation():
    event_id = "p2p_credits:frozen-sender:7:123"
    db = {
        "users": {
            "frozen-sender": {"frozen": True, "wallet": {"credits": 90.0}},
            "recipient": {"wallet": {"credits": 15.0}},
        },
        "ledger": [
            {
                "uid": "frozen-sender",
                "before": 100.0,
                "amount": -10.0,
                "after": 90.0,
                "reason": "p2p:credits_sent",
                "meta": {"recipient": "recipient", "event_id": event_id},
            },
            {
                "uid": "recipient",
                "before": 5.0,
                "amount": 10.0,
                "after": 15.0,
                "reason": "p2p:credits_received",
                "meta": {"sender": "frozen-sender", "event_id": event_id},
            },
        ],
    }
    before = copy.deepcopy(db)
    bot = FakeBot()
    ui_exchange_handler.register(bot)

    with patch.object(
        ui_exchange_handler.state_manager,
        "atomic_update",
        side_effect=lambda mutate: mutate(db),
    ):
        bot.handlers["p2p_credits"](_message())

    assert db == before
    assert bot.replies
    assert "already completed" in bot.replies[-1].lower()


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
