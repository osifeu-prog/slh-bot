import json

def _clip(value, limit):
    text = str(value if value is not None else "")
    text = text.replace("\x00", "").strip()
    if len(text) > limit:
        return text[:limit - 1] + "…"
    return text or "לא ידוע"

def register(bot):
    @bot.message_handler(commands=["me"])
    def me_cmd(message):
        uid = str(message.from_user.id)

        try:
            with open("state/db.json", encoding="utf-8") as f:
                data = json.load(f)

            users = data.get("users", {})
            user = users.get(uid, {})

            if not user:
                bot.reply_to(
                    message,
                    "❌ לא נמצאה הרשמה. השתמש ב-/join"
                )
                return

            name = _clip(user.get("name", "לא ידוע"), 80)
            role = _clip(user.get("role", "user"), 40)
            joined = _clip(user.get("joined", "לא ידוע"), 40)

            txt = (
                "[בס\"ד]\n\n"
                "👤 פרופיל SLH\n"
                f"• ID: {uid}\n"
                f"• שם: {name}\n"
                f"• תפקיד: {role}\n"
                f"• הצטרף: {joined}"
            )

            # Telegram-safe hard limit.
            bot.reply_to(message, txt[:3500])

        except Exception:
            # Never expose a large exception or internal state to Telegram.
            try:
                bot.reply_to(
                    message,
                    "❌ /me נתקל בתקלה פנימית. נסה שוב."
                )
            except Exception:
                pass
