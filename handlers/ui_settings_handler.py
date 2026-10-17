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
            f"🌐 שפה: {prefs['language']}\n"
            f"🔔 עדכוני התקדמות: {prefs['notification_level']}\n\n"
            "לשינוי ערכה: /theme <calm|system|light|contrast>\n"
            "לעדכוני התקדמות: /notifications <off|milestones|all>",
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

    @bot.message_handler(commands=["notifications", "stop_notifications"])
    def notifications_cmd(message):
        uid = str(message.from_user.id)
        parts = (message.text or "").split(maxsplit=1)
        value = parts[1].strip().lower() if len(parts) > 1 else ""
        command = parts[0].split("@")[0].lower() if parts else ""
        if command == "/stop_notifications" and not value:
            value = "off"
        if not value:
            prefs = get_preferences(uid)
            bot.reply_to(
                message,
                "🔔 הגדרות עדכוני התקדמות\n\n"
                f"מצב נוכחי: {prefs['notification_level']}\n"
                "/notifications off — ללא עדכוני התקדמות יזומים\n"
                "/notifications milestones — רק אבני דרך, חסימות, השלמה או פעולה נדרשת\n"
                "/notifications all — כל עדכוני ההתקדמות\n\n"
                "תשובות ישירות לפקודות שלך והודעות אבטחה קריטיות אינן מושתקות.",
                parse_mode=None,
            )
            return
        try:
            from core.ui_preferences import validate_notification_level
            level = validate_notification_level(value)
            prefs = set_preferences(uid, notification_level=level)
        except ValueError:
            bot.reply_to(
                message,
                "❌ ערך לא תקין. השתמש ב-/notifications off, /notifications milestones או /notifications all.",
                parse_mode=None,
            )
            return
        bot.reply_to(
            message,
            f"✅ נשמר: עדכוני התקדמות = {prefs['notification_level']}.\n"
            "ההגדרה נשמרת ב-state/db.json; היא חלה על שולחי עדכונים יזומים שמכבדים את מדיניות ההתראות.",
            parse_mode=None,
        )
