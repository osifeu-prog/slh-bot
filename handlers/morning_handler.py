from datetime import datetime

def register(bot, context):

    @bot.message_handler(commands=["morning"])
    def morning(message):
        now = datetime.now().strftime("%d/%m/%Y %H:%M")

        bot.send_message(
            message.chat.id,
            f"🌅 דוח פתיחת יום SLH\n\nזמן: {now}\nמערכת: פעילה ✅"
        )
