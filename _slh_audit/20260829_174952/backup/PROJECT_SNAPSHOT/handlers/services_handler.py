import json
from pathlib import Path

def register(bot, context=None):
    @bot.message_handler(commands=["services"])
    def services(m):
        db = json.loads(Path("state/db.json").read_text(encoding="utf-8"))
        svc = db.get("system_services", {})
        if not svc:
            bot.reply_to(m, "אין שירותי מערכת זמינים.")
            return
        lines = ["🛠 שירותי מערכת:", ""]
        for name, info in svc.items():
            status = info.get("status", "active")
            role = info.get("role", "unknown")
            perm = ", ".join(info.get("permissions", []))
            lines.append(f"• {name} [{status}] – {role}")
            if perm:
                lines.append(f"  הרשאות: {perm}")
        bot.reply_to(m, "\n".join(lines))
