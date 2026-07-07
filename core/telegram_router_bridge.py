from core.command_router import register_command


def extract_commands(bot):
    count = 0

    handlers = getattr(bot, "message_handlers", [])

    for handler in handlers:
        try:
            commands = getattr(handler, "commands", None)

            if not commands:
                continue

            callback = getattr(handler, "callback", None)

            if not callback:
                continue

            for cmd in commands:
                register_command(cmd, callback)
                count += 1

        except Exception as e:
            print("bridge error:", e)

    return count
