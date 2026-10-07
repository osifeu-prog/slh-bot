COMMANDS = {}

def slh_menu(message, bot):
    bot.send_message(
        message.chat.id,
        "🧠 SLH CONTROL CENTER\n\n"
        "/morning - דוח פתיחת יום\n"
        "/task - ניהול משימות\n"
        "/status - מצב מערכת"
    )

def register(bot, context=None):
    COMMANDS["slh"] = slh_menu

