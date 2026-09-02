from services import task_service
import json
from core import economy_bridge
from core import reward_engine


COMMANDS = {}

TASK_FILE = "state/db.json"


def load_db():
    with open(TASK_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_db(data):
    with open(TASK_FILE, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False
        )


def task(message, bot):

    db = load_db()

    tasks = db.get("tasks", {})

    if not tasks:
        bot.send_message(
            message.chat.id,
            "אין משימות"
        )
        return


    txt = "📋 משימות:\n\n"

    for key, t in tasks.items():

        done = (
            message.from_user.id
            in t.get("done_by", [])
        )

        status = "✅" if done else "⬜"

        progress = t.get("progress", 0)
        task_status = t.get("status", "active")
        txt += (
            f"{status} {key}: "
            f"{t.get('title', t.get('desc', '?'))} "
            f"[{task_status}] {progress}%\n"
        )


    bot.send_message(
        message.chat.id,
        txt
    )


def task_done(message, bot):

    from core import economy_service

    args = message.text.split()

    if len(args) < 2:
        bot.send_message(
            message.chat.id,
            "שימוש: /task_done task_1"
        )
        return

    task_id = args[1]
    uid = message.from_user.id

    try:
        result = economy_service.complete_task(
            uid=uid,
            task_id=task_id,
            meta={
                "source": "task_handler",
                "telegram_user_id": str(uid),
            },
        )

    except ValueError as e:

        reason = str(e)

        if reason == "TASK_NOT_FOUND":
            bot.send_message(
                message.chat.id,
                "❌ משימה לא קיימת"
            )
            return

        if reason == "TASK_ALREADY_COMPLETED":
            bot.send_message(
                message.chat.id,
                "כבר השלמת משימה זו"
            )
            return

        if reason == "USER_NOT_FOUND":
            bot.send_message(
                message.chat.id,
                "❌ המשתמש אינו רשום. יש לבצע /join."
            )
            return

        bot.send_message(
            message.chat.id,
            "❌ השלמת המשימה נחסמה."
        )
        print(f"[TASK] task_done blocked: {e}")
        return

    except Exception as e:

        bot.send_message(
            message.chat.id,
            "❌ השלמת המשימה נכשלה בבטחה."
        )
        print(f"[TASK] task_done error: {e}")
        return

    reward = result.get("reward", 0)

    bot.send_message(
        message.chat.id,
        f"🎉 משימה הושלמה!\n"
        f"+{reward} קרדיטים"
    )


def task_add(message, bot):

    args = message.text.split(maxsplit=1)

    if len(args) < 2:
        bot.send_message(
            message.chat.id,
            "שימוש: /task_add <משימה>"
        )
        return


    task = task_service.add_task(args[1])

    bot.send_message(
        message.chat.id,
        f"✅ Task Added\nID: {task['id']}"
    )



def register(bot, context=None):

    COMMANDS["task"] = task
    COMMANDS["task_done"] = task_done
    COMMANDS["task_add"] = task_add


    @bot.message_handler(commands=["task"])
    def task_telegram(message):
        task(message, bot)


    @bot.message_handler(commands=["task_done"])
    def task_done_telegram(message):
        task_done(message, bot)


    @bot.message_handler(commands=["task_add"])
    def task_add_telegram(message):
        task_add(message, bot)
