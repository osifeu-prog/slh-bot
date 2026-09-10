import uuid
from datetime import datetime, timezone

import state_manager
from core import task_completion_service

COMMANDS = {}
TASK_FILE = "state/db.json"


def load_db():
    return state_manager.load_db()


def save_db(data):
    return state_manager.save_db(data)


def task(message, bot):
    db = load_db()
    tasks = db.get("tasks", {})
    if not tasks:
        bot.send_message(message.chat.id, "אין משימות")
        return
    txt = "📋 משימות:\n\n"
    for key, t in tasks.items():
        done = str(message.from_user.id) in [str(x) for x in t.get("done_by", [])]
        status = "✅" if done else "⬜"
        progress = t.get("progress", 0)
        task_status = t.get("status", "active")
        txt += f"{status} {key}: {t.get('title', t.get('desc', '?'))} [{task_status}] {progress}%\n"
    bot.send_message(message.chat.id, txt)


def task_done(message, bot):
    args = message.text.split()
    if len(args) < 2:
        bot.send_message(message.chat.id, "שימוש: /task_done task_1")
        return
    task_id = args[1]
    uid = message.from_user.id
    try:
        result = task_completion_service.complete_task(
            uid=uid,
            task_id=task_id,
            meta={"source": "task_handler", "telegram_user_id": str(uid)},
        )
    except ValueError as e:
        reason = str(e)
        if reason == "TASK_NOT_FOUND":
            bot.send_message(message.chat.id, "❌ משימה לא קיימת")
            return
        if reason == "TASK_ALREADY_COMPLETED":
            bot.send_message(message.chat.id, "כבר השלמת משימה זו")
            return
        if reason == "USER_NOT_FOUND":
            bot.send_message(message.chat.id, "❌ המשתמש אינו רשום. יש לבצע /join.")
            return
        bot.send_message(message.chat.id, "❌ השלמת המשימה נחסמה.")
        print(f"[TASK] task_done blocked: {e}")
        return
    except Exception as e:
        bot.send_message(message.chat.id, "❌ השלמת המשימה נכשלה בבטחה.")
        print(f"[TASK] task_done error: {e}")
        return
    reward = result.get("reward", 0)
    if result.get("reward_status") == "pending":
        bot.send_message(message.chat.id, f"🎉 משימה הושלמה!\n+{reward} קרדיטים\n⚠️ התגמול ממתין לעיבוד חוזר.")
        return
    bot.send_message(message.chat.id, f"🎉 משימה הושלמה!\n+{reward} קרדיטים")


def task_add(message, bot):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.send_message(message.chat.id, "שימוש: /task_add <משימה>")
        return
    description = args[1].strip()
    if not description:
        bot.send_message(message.chat.id, "שימוש: /task_add <משימה>")
        return
    task_id = "task_" + uuid.uuid4().hex

    def mutate(db):
        tasks = db.setdefault("tasks", {})
        if task_id in tasks:
            raise RuntimeError("TASK_ID_COLLISION")
        tasks[task_id] = {
            "id": task_id, "title": description, "desc": description,
            "status": "active", "progress": 0, "reward": 0, "done_by": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        return dict(tasks[task_id])

    try:
        task_data = state_manager.atomic_update(mutate)
    except Exception as e:
        bot.send_message(message.chat.id, "❌ יצירת המשימה נכשלה.")
        print(f"[TASK] task_add error: {e}")
        return
    bot.send_message(message.chat.id, f"✅ Task Added\nID: {task_data['id']}")


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
