import state_manager

def init(bot):
    @bot.message_handler(commands=['debug_commands'])
    def debug_commands(m):
        from admin_utils import is_admin
        if not is_admin(m):
            return
        handlers = []
        for handler in bot.message_handlers:
            h = handler
            handlers.append(str(h.get("function", "unknown")))
        bot.reply_to(m, "Registered handlers:\n" + "\n".join(handlers[:50]))
