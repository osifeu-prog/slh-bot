"""User-controlled delivery settings for non-critical progress notifications."""
from core.notification_preferences import (
    get_notification_preferences,
    set_progress_updates,
)


def register(bot):
    @bot.message_handler(commands=["stop_notifications"])
    def stop_notifications(message):
        uid = str(getattr(getattr(message, "from_user", None), "id", "") or "")
        result = set_progress_updates(uid, False)
        if not result.get("ok"):
            bot.reply_to(message, "⚠️ לא הצלחתי לשמור את ההעדפה. לא שיניתי את מצב ההתראות.")
            return
        bot.reply_to(
            message,
            "🔕 נשמר: עדכוני התקדמות שגרתיים והודעות ציון דרך לא יישלחו אליך "
            "דרך מסלול ההתראות שמכבד את ההעדפה.\n"
            "הודעות שאתה מבקש ישירות, אישורי פעולה, תשלומים, אבטחה וחסימות פיננסיות "
            "יישארו פעילות. הפקודה אינה עוצרת תהליך אוטומטי ואינה משנה הרשאות.",
        )

    @bot.message_handler(commands=["resume_notifications", "start_notifications"])
    def resume_notifications(message):
        uid = str(getattr(getattr(message, "from_user", None), "id", "") or "")
        result = set_progress_updates(uid, True)
        if not result.get("ok"):
            bot.reply_to(message, "⚠️ לא הצלחתי לשמור את ההעדפה. לא שיניתי את מצב ההתראות.")
            return
        bot.reply_to(message, "🔔 נשמר: עדכוני התקדמות שגרתיים מופעלים שוב.")

    @bot.message_handler(commands=["notification_status", "notifications"])
    def notification_status(message):
        uid = str(getattr(getattr(message, "from_user", None), "id", "") or "")
        result = get_notification_preferences(uid)
        if not result.get("ok"):
            bot.reply_to(message, "⚠️ מצב ההתראות אינו זמין כרגע; לא בוצע שינוי.")
            return
        progress = "מופעלים" if result.get("progress_updates_enabled") else "מושתקים"
        bot.reply_to(
            message,
            "🔔 העדפות התראות\n"
            f"עדכוני התקדמות שגרתיים: {progress}\n"
            "התראות אבטחה, תשלום, שערים פיננסיים ופעולות שנדרשת לגביהן החלטה: פעילות תמיד.",
        )
