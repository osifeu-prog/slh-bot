from core.command_router import register_command


def extract_commands(bot):
    count = 0

    handlers = getattr(bot, "message_handlers", [])

    print("🔎 Telegram handlers found:", len(handlers))

    for handler in handlers:
        try:
            if not isinstance(handler, dict):
                continue

            commands = handler.get("filters", {}).get("commands")

            callback = handler.get("function")

            if not commands or not callback:
                continue

            for cmd in commands:
                register_command(cmd, callback)
                count += 1
                print(f"🔗 bridged /{cmd}")

        except Exception as e:
            print("bridge error:", e)

    return count
