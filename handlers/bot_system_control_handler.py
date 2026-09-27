"""Owner-only unified Bot Control surface."""
from core.authority import is_owner
from core.bot_system_registry import report


def register(bot):
    @bot.message_handler(commands=["bots", "botcontrol"])
    def bots_cmd(message):
        if not is_owner(message):
            bot.reply_to(message, "⛔️ Owner only")
            return
        bot.reply_to(message, report(owner_id=str(message.from_user.id)))

    print("✅ bot_system_control handler registered")
