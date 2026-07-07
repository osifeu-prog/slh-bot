def register(bot, context):

    @bot.message_handler(commands=["slh"])
    def slh_menu(message):
        bot.send_message(
            message.chat.id,
            "🧠 SLH CONTROL CENTER\n\n"
            "/morning - דוח פתיחת יום\n"
            "/task - ניהול משימות\n"
            "/status - מצב מערכת"
        )
