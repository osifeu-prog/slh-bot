from handlers import mission_handler


class FakeBot:
    def __init__(self):
        self.handlers = []
        self.replies = []

    def message_handler(self, **kwargs):
        def decorator(fn):
            self.handlers.append((kwargs, fn))
            return fn
        return decorator

    def reply_to(self, message, text):
        self.replies.append(text)


class FakeLifecycle:
    def __init__(self):
        self.load_calls = 0

    def load_state(self):
        self.load_calls += 1
        return (
            {
                "missions": [
                    {
                        "id": "7",
                        "status": "open",
                        "desc": "Read-only audit task",
                        "assigned_to": None,
                        "reward": 0,
                    }
                ]
            },
            {},
        )


class Message:
    text = "/mission"


def test_bare_mission_command_lists_missions_without_mutating():
    bot = FakeBot()
    lifecycle = FakeLifecycle()
    mission_handler.register(bot, {"mission_lifecycle": lifecycle})

    options, handler = bot.handlers[0]
    assert options["commands"] == ["mission"]
    handler(Message())

    assert lifecycle.load_calls == 1
    assert len(bot.replies) == 1
    assert "#7: Read-only audit task" in bot.replies[0]
    assert "שימוש:" not in bot.replies[0]
