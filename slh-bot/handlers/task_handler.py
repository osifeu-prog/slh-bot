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
            txt += f"{t['id']}. {t.get('desc', t.get('text',''))} [{t['status']}]\n"

        bot.send_message(message.chat.id, txt)
        return

    task_service.add_task(args[1])
    bot.send_message(
        message.chat.id,
        "✅ המשימה נוספה למערכת"
    )


def task_add(message, bot):
    args = message.text.split(maxsplit=1)

    if len(args) < 2:
        bot.send_message(
            message.chat.id,
            "❌ שימוש:\n/task_add <משימה>"
        )
        return

    task = task_service.add_task(args[1])

    bot.send_message(
        message.chat.id,
        f"✅ Task Added\nID: {task['id']}\n{task.get('desc', task.get('text',''))}"
    )


def register(bot, context=None):
    COMMANDS["task"] = task
    COMMANDS["task_add"] = task_add

    @bot.message_handler(commands=["task"])
    def task_telegram(message):
        task(message, bot)

    @bot.message_handler(commands=["task_add"])
    def task_add_telegram(message):
        task_add(message, bot)

# deploy-check-122
