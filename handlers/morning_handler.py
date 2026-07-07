from datetime import datetime

COMMANDS = {}

def morning(message, bot):
    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    bot.send_message(
        message.chat.id,
        f"🌅 דוח פתיחת יום SLH\n\nזמן: {now}\nמערכת: פעילה ✅"
    )

def register(bot, context=None):
    COMMANDS["morning"] = morning

    @bot.message_handler(commands=["morning"])
    def morning_telegram(message):
        morning(message, bot)
