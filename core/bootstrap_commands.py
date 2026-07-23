from core.command_router import register_command, HANDLERS
import importlib
import telebot

def init(bot):

    modules = [
        "ask_handler",
        "admin_handler",
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

            # ׳¨׳’׳™׳ - Telegram decorators
            if hasattr(m, "register"):
                try:
                    m.register(bot)
                except Exception as e:
                    print(f"ג ן¸ {name} telegram register: {e}")

            # ׳—׳“׳© - Router
            if hasattr(m, "COMMANDS"):
                for cmd, fn in m.COMMANDS.items():
                    register_command(cmd, fn)

            loaded += 1

        except Exception as e:
            print(f"ג {name}: {e}")

    print(f"נ“¦ Command modules loaded: {loaded}")
    print(f"נ§­ Router commands: {len(HANDLERS)}")
