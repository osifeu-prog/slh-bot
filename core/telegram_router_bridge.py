from core.command_router import register_command
import re


def extract_commands(bot):
    count = 0

    for handler in getattr(bot, "message_handlers", []):
        try:
            commands = handler.get("commands")
        except:
            commands = None

        if not commands:
            continue

        callback = getattr(handler, "callback", None)

        if not callback:
            try:
                callback = handler["function"]
            except:
                pass

        if not callback:
            continue

        for cmd in commands:
            register_command(cmd, callback)
            count += 1

    return count
