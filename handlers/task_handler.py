from services import task_service

COMMANDS = {}

def task(message, bot):
    args = message.text.split(maxsplit=1)

    if len(args) == 1 or (len(args) > 1 and args[1].strip().lower() == "list"):
        tasks = task_service.list_tasks()

        if not tasks:
            bot.send_message(message.chat.id, "📋 אין משימות")
            return

        txt = "📋 משימות:\n\n"
        for t in tasks:
            txt += f"{t['id']}. {t['text']} [{t['status']}]\n"

        bot.send_message(message.chat.id, txt)
        return

    task_service.add_task(args[1])
    bot.send_message(
        message.chat.id,
        "✅ המשימה נוספה למערכת"
    )

def register(bot, context=None):
    COMMANDS["task"] = task

    @bot.message_handler(commands=["task"])
    def task_telegram(message):
        task(message, bot)
