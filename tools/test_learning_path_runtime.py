import handlers.loader
import learning_path


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


print("=== DIRECT MODULE REGISTRATION ===")

bot = DummyBot()

learning_path.register_learning_path(bot)

commands = []
for item in bot.message_handlers:
    if item["commands"]:
        commands.extend(item["commands"])

print("DIRECT_COURSE_SLH_REGISTERED=", "course_slh" in commands)
print("DIRECT_AGENT_SUBMIT_REGISTERED=", "agent_submit" in commands)
print("DIRECT_SETNAME_REGISTERED=", "setname" in commands)
print("DIRECT_MESSAGE_HANDLER_COUNT=", len(bot.message_handlers))
print("DIRECT_CALLBACK_HANDLER_COUNT=", len(bot.callback_query_handlers))

if "course_slh" not in commands:
    raise SystemExit("FAIL: direct /course_slh registration missing")

if "agent_submit" not in commands:
    raise SystemExit("FAIL: direct /agent_submit registration missing")

if "setname" not in commands:
    raise SystemExit("FAIL: direct /setname registration missing")

print("DIRECT_REGISTRATION=PASS")

print("=== LOADER STRUCTURE ===")

loader_source = open("handlers/loader.py", encoding="utf-8").read()

if '("learning_path", "learning_path")' not in loader_source:
    raise SystemExit("FAIL: learning_path loader entry missing")

if 'elif hasattr(m, "register_learning_path"):' not in loader_source:
    raise SystemExit("FAIL: register_learning_path loader branch missing")

if "m.register_learning_path(bot)" not in loader_source:
    raise SystemExit("FAIL: register_learning_path(bot) call missing")

print("LOADER_REGISTRATION_STRUCTURE=PASS")
print("LEARNING_PATH_RUNTIME_REGISTRATION=PASS")
