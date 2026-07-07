from core.command_router import register_command, HANDLERS
import importlib
import telebot

def init(bot):

    modules = [
        "ask_handler",
        "admin_handler",
        "learn_handlers",
        "course_handlers",
        "project_commands",
        "monitor_handler",
        "report_handler",
        "help_handler",
    ]

    loaded = 0

    for name in modules:
        try:
            m = importlib.import_module(name)

            # רגיל - Telegram decorators
            if hasattr(m, "register"):
                try:
                    m.register(bot)
                except Exception as e:
                    print(f"⚠️ {name} telegram register: {e}")

            # חדש - Router
            if hasattr(m, "COMMANDS"):
                for cmd, fn in m.COMMANDS.items():
                    register_command(cmd, fn)

            loaded += 1

        except Exception as e:
            print(f"❌ {name}: {e}")

    print(f"📦 Command modules loaded: {loaded}")
    print(f"🧭 Router commands: {len(HANDLERS)}")
