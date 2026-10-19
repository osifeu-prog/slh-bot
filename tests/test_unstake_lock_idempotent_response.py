from types import SimpleNamespace
from unittest.mock import patch

from handlers import staking_handler


def test_unstake_lock_does_not_claim_success_when_position_already_unlocked():
    handlers = {}

    class FakeBot:
        def __init__(self):
            self.replies = []

        def message_handler(self, **kwargs):
            def decorator(fn):
                for command in kwargs.get("commands", []):
                    handlers[command] = fn
                return fn
            return decorator

        def reply_to(self, message, text):
            self.replies.append((message, text))

    bot = FakeBot()
    staking_handler.register(bot)
    message = SimpleNamespace(
        text="/unstake_lock sp_example",
        from_user=SimpleNamespace(id=12345),
    )
    position = {"id": "sp_example", "uid": "12345", "amount": 100.0}
    result = {"status": "already_unlocked", "credits": 110.0, "staked": 0.0}

    with patch.object(staking_handler, "get_position", return_value=position), patch.object(
        staking_handler.staking_service, "unstake_locked", return_value=result
    ) as unstake:
        handlers["unstake_lock"](message)

    unstake.assert_called_once()
    assert bot.replies == [(message, "הפוזיציה כבר שוחררה.")]
