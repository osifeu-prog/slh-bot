from handlers import staking_revenue_handler


class FakeBot:
    def __init__(self):
        self.handlers = []

    def message_handler(self, **kwargs):
        def decorator(fn):
            self.handlers.append((kwargs, fn))
            return fn
        return decorator

    def reply_to(self, message, text):
        message.replied = text


class Message:
    def __init__(self, uid="u1", text="/stake_revenue 10"):
        self.from_user = type("U", (), {"id": uid})()
        self.text = text
        self.replied = None


def test_revenue_share_commands_are_read_only_guarded():
    bot = FakeBot()
    staking_revenue_handler.register(bot)

    assert len(bot.handlers) == 1
    commands = bot.handlers[0][0]["commands"]
    assert commands == ["stake_revenue", "claim_revenue", "my_stake"]

    for command in ("/stake_revenue 10", "/claim_revenue", "/my_stake"):
        msg = Message(text=command)
        bot.handlers[0][1](msg)
        assert "Revenue Share staking" in msg.replied
        assert "לא פעיל" in msg.replied
