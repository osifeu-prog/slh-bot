import json
import time

from core.identity import OWNER_TELEGRAM_ID

MAX_BROADCAST_LENGTH = 4096
SEND_DELAY_SECONDS = 0.05


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
        if not message_text:
            bot.reply_to(m, "Usage: /broadcast <text>")
            return
        if len(message_text) > MAX_BROADCAST_LENGTH:
            bot.reply_to(
                m,
                f"❌ Broadcast message is too long. Maximum: {MAX_BROADCAST_LENGTH} characters.",
            )
            return

        try:
            db = json.load(open("state/db.json", encoding="utf-8"))
        except Exception as exc:
            bot.reply_to(m, f"DB error: {type(exc).__name__}")
            return

        users = db.get("users", {})
        sent = 0
        failed = []

        for uid in users.keys():
            try:
                bot.send_message(uid, message_text)
                sent += 1
            except Exception:
                failed.append(str(uid))
            if SEND_DELAY_SECONDS:
                time.sleep(SEND_DELAY_SECONDS)

        bot.reply_to(
            m,
            f"✅ Broadcast sent to {sent} users.\n"
            f"Failed: {len(failed)}",
        )
