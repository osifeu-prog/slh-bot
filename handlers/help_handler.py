def register(bot):
    @bot.message_handler(commands=["faq"])
    def faq_cmd(msg):
        try:
            from core.faq_service import telegram_faq
            bot.reply_to(msg, telegram_faq())
        except Exception:
            bot.reply_to(msg, "FAQ לא זמין כרגע.")

    @bot.message_handler(commands=["help"])
    def help_cmd(msg):
        try:
            from core.faq_service import telegram_faq
            bot.reply_to(msg, telegram_faq())
        except Exception:
            bot.reply_to(msg, "העזרה לא זמינה כרגע.")

    @bot.message_handler(commands=["allcommands", "commands", "comands"])
    def commands_cmd(msg):
        try:
            from handlers.commands_catalog_handler import reply_with_catalog
            reply_with_catalog(bot, msg)
        except Exception as exc:
            bot.reply_to(msg, f"לא ניתן לבנות כרגע קטלוג פקודות: {type(exc).__name__}")
