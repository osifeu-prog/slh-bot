import json, time
from pathlib import Path

LOG_PATH = Path("state/exec_log.json")

def register(bot):
    @bot.message_handler(commands=["exec_log"])
    def exec_log(m):
        if not LOG_PATH.exists():
            bot.reply_to(m, "📄 אין לוגים עדיין.")
            return
        try:
            logs = json.loads(LOG_PATH.read_text(encoding="utf-8"))
        except:
            bot.reply_to(m, "❌ שגיאה בקריאת הלוג.")
            return

        text = "📓 EXEC LOG (אחרונים):\n\n"
        for entry in logs[-10:]:
            ts = time.strftime("%d/%m %H:%M:%S", time.localtime(entry["ts"]))
            text += f"🕒 {ts}\n"
            text += f"📌 CMD: {entry['cmd']}\n"
            text += f"📤 OUTPUT:\n{entry['output'][:300]}\n\n"

        bot.reply_to(m, text[:3500])
