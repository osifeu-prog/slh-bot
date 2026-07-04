from core.command_registry_loader import load_commands_registry

# handlers registry in runtime
HANDLERS = {}

def register_command(cmd, func):
    HANDLERS[cmd] = func


def dispatch_command(cmd, message, bot):
    registry = load_commands_registry()

    if cmd not in registry:
        bot.reply_to(message, "❌ Unknown command")
        return

    if cmd not in HANDLERS:
        bot.reply_to(message, "⚠️ Command not implemented")
        return

    return HANDLERS[cmd](message, bot)
