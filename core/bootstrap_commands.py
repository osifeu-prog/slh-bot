from core.command_router import register_command, HANDLERS

import importlib


def _register_module_commands(module):
    """
    Supports modules that expose:
    register_commands(register_command)
    """

    if hasattr(module, "register_commands"):
        module.register_commands(register_command)


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

    loaded = []

    for name in modules:
        try:
            m = importlib.import_module(name)

            # Existing Telegram registration
            if hasattr(m, "register"):
                try:
                    m.register(bot)
                except Exception as e:
                    print(f"⚠️ {name} register(bot) failed: {e}")

            # New router registration
            _register_module_commands(m)

            loaded.append(name)

        except Exception as e:
            print(f"❌ Command module failed {name}: {e}")

    print(f"📦 Command modules loaded: {len(loaded)}")
    print(f"🧭 Router commands: {len(HANDLERS)}")
