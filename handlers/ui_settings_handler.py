"""User UI settings commands for Telegram."""
from core.ui_preferences import get_preferences, set_preferences, theme_choices, validate_theme


def _themes_text(current: str) -> str:
    lines = ["🎨 SLH OS — ערכת תצוגה", ""]
    for item in theme_choices():
        marker = "✅" if item["id"] == current else "⚪"
        lines.append(f"{marker} /theme {item['id']} — {item['label']}: {item['description']}")
    lines.append("")
    lines.append("אפשרויות נוספות: /settings")
    return "\n".join(lines)


def register(bot):
    @bot.message_handler(commands=["settings"])
    def settings_cmd(message):
        uid = str(message.from_user.id)
        prefs = get_preferences(uid)
        bot.reply_to(
            message,
            "⚙️ SLH OS — הגדרות אישיות\n\n"
            f"🎨 ערכת תצוגה: {prefs['theme']}\n"
            f"📐 מצב קומפקטי: {'ON' if prefs['compact'] else 'OFF'}\n"
            f"🌐 שפה: {prefs['language']}\n\n"
            "לשינוי ערכה: /theme <calm|system|light|contrast>",
        )

    @bot.message_handler(commands=["theme"])
    def theme_cmd(message):
        uid = str(message.from_user.id)
        parts = (message.text or "").split(maxsplit=1)
        value = parts[1].strip() if len(parts) > 1 else ""
        if not value:
            prefs = get_preferences(uid)
            bot.reply_to(message, _themes_text(prefs["theme"]))
            return
        try:
            prefs = set_preferences(uid, theme=validate_theme(value))
        except Exception:
            bot.reply_to(message, "❌ ערכת תצוגה לא תקינה. השתמש ב-/theme כדי לראות את האפשרויות.")
            return
        bot.reply_to(message, f"✅ ערכת התצוגה נשמרה: {prefs['theme']}\nפתח /miniapp מחדש כדי לראות את הבחירה.")
