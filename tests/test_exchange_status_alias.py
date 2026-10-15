from handlers import system_checks_handler as target


class FakeBot:
    def __init__(self):
        self.handlers = {}

    def message_handler(self, commands=None, **kwargs):
        def decorator(handler):
            for command in commands or []:
                self.handlers[str(command).lstrip("/")] = handler
            return handler
        return decorator

    def reply_to(self, message, text, **kwargs):
        pass


def test_exchange_status_is_an_alias_of_the_canonical_read_only_check():
    bot = FakeBot()
    target.register(bot)

    assert bot.handlers["exchange_status"] is bot.handlers["check_exchange"]
