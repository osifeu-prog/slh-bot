import json
from core.identity import OWNER_TELEGRAM_ID


def register(bot):
    @bot.message_handler(commands=["broadcast"])
    def broadcast_cmd(m):
        if int(m.from_user.id) != int(OWNER_TELEGRAM_ID):
            bot.reply_to(m, "⛔ OWNER only")
            return

        parts = (m.text or "").split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /broadcast <text>")
            return

        message_text = parts[1].strip()

        try:
            db = json.load(open("state/db.json", encoding="utf-8"))
        except Exception as e:
            bot.reply_to(m, f"DB error: {e}")
            return

        users = db.get("users", {})
        sent = 0
        failed = []

        for uid in users.keys():
            try:
                bot.send_message(uid, message_text)
                sent += 1
            except Exception as e:
                failed.append(f"{uid}: {type(e).name} - {e}")

        bot.reply_to(
            m,
            f"✅ Broadcast sent to {sent} users.\n"
            f"Failed: {len(failed)}"
        )
