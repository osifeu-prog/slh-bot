from pathlib import Path
from core.progress_tracker import progress_report, get_work_log, start_work, stop_work

def register_handlers(bot, context=None):
    @bot.message_handler(commands=["progress"])
    def progress_cmd(message):
        bot.reply_to(message, progress_report())

    @bot.message_handler(commands=["startwork"])
    def startwork_cmd(message):
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(message, "שימוש: /startwork <שם משימה>")
            return
        task_name = parts[1].strip()
        start_work(task_name, message.from_user.id)
        bot.reply_to(message, f"⏱️ מדידת זמן החלה עבור: {task_name}")

    @bot.message_handler(commands=["stopwork"])
    def stopwork_cmd(message):
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(message, "שימוש: /stopwork <שם משימה>")
            return
        task_name = parts[1].strip()
        if stop_work(task_name, message.from_user.id):
            bot.reply_to(message, f"⏱️ מדידת זמן הסתיימה עבור: {task_name}")
        else:
            bot.reply_to(message, f"לא נמצאה משימה פעילה: {task_name}")

    @bot.message_handler(commands=["worklog"])
    def worklog_cmd(message):
        entries = get_work_log(message.from_user.id)
        if not entries:
            bot.reply_to(message, "אין רשומות זמן.")
            return
        text = "📋 יומן עבודה:\n\n"
        for e in entries[-10:]:
            start = e.get("start", "?")
            stop = e.get("stop", "פעיל")
            text += f"• {e.get('task')}: {start} → {stop}\n"
        bot.reply_to(message, text[:3500])
