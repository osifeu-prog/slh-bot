from handlers.system_checks_handler import register


class _FakeBot:
    def __init__(self):
        self.registered = []

    def message_handler(self, commands=None, **kwargs):
        def decorate(fn):
            self.registered.append((commands, fn))
            return fn
        return decorate

    def reply_to(self, message, text, **kwargs):
        raise AssertionError("handlers are registered, not executed in this test")


def test_single_go_live_report_command_is_registered():
    bot = _FakeBot()
    register(bot)

    commands = {
        command
        for registered, _handler in bot.registered
        for command in (registered or [])
    }
    assert "go_live_report" in commands
