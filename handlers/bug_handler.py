"""User bug-report command.

Stores structured bug reports in the canonical runtime DB so reports can
be reviewed without relying on ad-hoc /exec mutations.
"""
from datetime import datetime, timezone

import state_manager


def register(bot):
    @bot.message_handler(commands=["bug"])
    def bug_cmd(message):
        raw = (message.text or "").split(maxsplit=1)
        if len(raw) < 2 or not raw[1].strip():
            bot.reply_to(message, "🐞 שימוש: /bug <תיאור התקלה>")
            return

        report_id = "BUG_%s_%s" % (
            datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
            message.message_id,
        )
        text = raw[1].strip()
        uid = str(message.from_user.id)

        def mutate(db):
            reports = db.setdefault("bug_reports", [])
            reports.append({
                "id": report_id,
                "uid": uid,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "text": text,
                "status": "open",
            })
            return report_id

        state_manager.atomic_update(mutate)
        bot.reply_to(message, f"🐞 הדיווח נקלט: {report_id}")

    print("bug_handler loaded")
