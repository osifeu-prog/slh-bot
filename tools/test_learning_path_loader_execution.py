import handlers.loader

class DummyBot:
    def __init__(self):
        self.message_handlers = []
        self.callback_query_handlers = []

    def message_handler(self, **kwargs):
        def decorator(fn):
            self.message_handlers.append({
                "function": fn,
                "commands": kwargs.get("commands"),
            })
            return fn
        return decorator

    def callback_query_handler(self, **kwargs):
        def decorator(fn):
            self.callback_query_handlers.append({
                "function": fn,
                "filter": kwargs.get("func"),
            })
            return fn
        return decorator

    def send_message(self, *args, **kwargs):
        pass

    def reply_to(self, *args, **kwargs):
        pass

    def answer_callback_query(self, *args, **kwargs):
        pass


class DummyContext:
    pass


bot = DummyBot()
context = DummyContext()

print("=== CALLING handlers.loader.load_handlers() ===")

handlers.loader.load_handlers(bot, context)

commands = []

for item in bot.message_handlers:
    if item["commands"]:
        commands.extend(item["commands"])

print("LOADER_COURSE_SLH=", "course_slh" in commands)
print("LOADER_AGENT_SUBMIT=", "agent_submit" in commands)
print("LOADER_SETNAME=", "setname" in commands)
print("LOADER_MESSAGE_HANDLER_COUNT=", len(bot.message_handlers))
print("LOADER_CALLBACK_HANDLER_COUNT=", len(bot.callback_query_handlers))

if "course_slh" not in commands:
    raise SystemExit("FAIL: loader did not register /course_slh")

if "agent_submit" not in commands:
    raise SystemExit("FAIL: loader did not register /agent_submit")

if "setname" not in commands:
    raise SystemExit("FAIL: loader did not register /setname")

print("AUTHORITATIVE_LOADER_EXECUTION=PASS")
