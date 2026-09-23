from core.progress_tracker import (
    get_work_log,
    pause_work,
    progress_report,
    resume_work,
    start_work,
    stop_work,
    work_report,
    work_status,
)


def register_handlers(bot, context=None):
    @bot.message_handler(commands=["progress"])
    def progress_cmd(message):
        bot.reply_to(message, progress_report())

    @bot.message_handler(commands=["startwork"])
    def startwork_cmd(message):
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(message, "שימוש: /startwork <שם משימה>")
            return
        task_name = parts[1].strip()
        if start_work(task_name, message.from_user.id):
            bot.reply_to(
                message,
                "⏱️ מדידת זמן החלה.\n\n"
                + work_status(message.from_user.id),
            )
        else:
            bot.reply_to(
                message,
                "⚠️ כבר קיימת מדידת זמן פעילה עבור המשימה הזו.",
            )

    @bot.message_handler(commands=["pausework"])
    def pausework_cmd(message):
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(message, "שימוש: /pausework <שם משימה>")
            return
        task_name = parts[1].strip()
        if pause_work(task_name, message.from_user.id):
            bot.reply_to(
                message,
                "⏸️ העבודה הושהתה.\n\n"
                + work_status(message.from_user.id),
            )
        else:
            bot.reply_to(message, f"לא נמצאה משימת עבודה פעילה: {task_name}")

    @bot.message_handler(commands=["resumework"])
    def resumework_cmd(message):
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(message, "שימוש: /resumework <שם משימה>")
            return
        task_name = parts[1].strip()
        if resume_work(task_name, message.from_user.id):
            bot.reply_to(
                message,
                "▶️ העבודה חודשה.\n\n"
                + work_status(message.from_user.id),
            )
        else:
            bot.reply_to(message, f"לא נמצאה משימת עבודה פעילה: {task_name}")

    @bot.message_handler(commands=["workstatus"])
    def workstatus_cmd(message):
        bot.reply_to(message, work_status(message.from_user.id))

    @bot.message_handler(commands=["stopwork"])
    def stopwork_cmd(message):
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(message, "שימוש: /stopwork <שם משימה>")
            return
        task_name = parts[1].strip()
        if stop_work(task_name, message.from_user.id):
            bot.reply_to(
                message,
                "⏹️ מדידת הזמן הסתיימה.\n\n"
                + work_report(message.from_user.id),
            )
        else:
            bot.reply_to(message, f"לא נמצאה משימה פעילה: {task_name}")

    @bot.message_handler(commands=["worklog"])
    def worklog_cmd(message):
        entries = get_work_log(message.from_user.id)
        if not entries:
            bot.reply_to(message, "אין רשומות זמן.")
            return

        text = "📋 יומן עבודה:\n\n"
        for entry in entries[-10:]:
            start = entry.get("start", "?")
            stop = entry.get("stop") or "פעיל"
            active = entry.get("active_seconds", 0) or 0
            wall = entry.get("wall_seconds", 0) or 0
            text += (
                f"• {entry.get('task', '—')}\n"
                f"  {start} → {stop}\n"
                f"  ⏱️ פעיל: {active:.0f}s | elapsed: {wall:.0f}s\n"
            )
        bot.reply_to(message, text[:3500])

    @bot.message_handler(commands=["report"])
    def report_cmd(message):
        bot.reply_to(message, work_report(message.from_user.id)[:3500])
