import handlers.loader

class DummyBot:
    def __init__(self):
        self.message_handlers = []
        self.callback_query_handlers = []
        self.pre_checkout_query_handlers = []
        self.inline_handlers = []
        self.chat_member_handlers = []

    def message_handler(self, **kwargs):
        def decorator(fn):
            self.message_handlers.append({
                "function": fn,
                "commands": kwargs.get("commands"),
                "filters": kwargs,
            })
            return fn
        return decorator

    def callback_query_handler(self, **kwargs):
        def decorator(fn):
            self.callback_query_handlers.append({
                "function": fn,
                "filter": kwargs.get("func"),
                "filters": kwargs,
            })
            return fn
        return decorator

    def pre_checkout_query_handler(self, **kwargs):
        def decorator(fn):
            self.pre_checkout_query_handlers.append({
                "function": fn,
                "filters": kwargs,
            })
            return fn
        return decorator

    def inline_handler(self, **kwargs):
        def decorator(fn):
            self.inline_handlers.append({
                "function": fn,
                "filters": kwargs,
            })
            return fn
        return decorator

    def chat_member_handler(self, **kwargs):
        def decorator(fn):
            self.chat_member_handlers.append({
                "function": fn,
                "filters": kwargs,
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

print("=== CALLING load_handlers() ===")

handlers.loader.load_handlers(bot, context)

commands = []

for item in bot.message_handlers:
    if item["commands"]:
        commands.extend(item["commands"])

checks = {
    "course_slh": "course_slh" in commands,
    "agent_submit": "agent_submit" in commands,
    "setname": "setname" in commands,
}

print("COURSE_SLH=", checks["course_slh"])
print("AGENT_SUBMIT=", checks["agent_submit"])
print("SETNAME=", checks["setname"])

print("MESSAGE_HANDLERS=", len(bot.message_handlers))
print("CALLBACK_HANDLERS=", len(bot.callback_query_handlers))
print("PRE_CHECKOUT_HANDLERS=", len(bot.pre_checkout_query_handlers))

if not all(checks.values()):
    raise SystemExit("FAIL: required Learning Path commands missing")

print("LEARNING_PATH_LOADER_RUNTIME=PASS")
print("FULL_MODULAR_LOADER_EXECUTION=PASS")
