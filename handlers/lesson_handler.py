from core import lesson_engine
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton


def register(bot):

    @bot.message_handler(commands=['lesson'])
    def lesson(m):
        parts = m.text.split()

        if len(parts) != 3:
            markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton(
                "✅ סיימתי את השיעור",
                callback_data=f"slh_finish_{course_id}_{stage}"
            )
        )
        markup.add(
            InlineKeyboardButton(
                "🎓 חזרה ל-Academy",
                callback_data="slh_academy"
            )
        )

        bot.send_message(
            m.chat.id,
            f"📘 {lesson['name']}\n\n"
            f"{lesson['content']}\n\n"
            "סיימת? לחץ על הכפתור למטה. 👇",
            reply_markup=markup
        )

    @bot.message_handler(commands=['finish'])
    def finish(m):
        parts = m.text.split()

        if len(parts) != 3:
            bot.reply_to(
                m,
                "שימוש:\n/finish bitcoin_mastery 1"
            )
            return

        uid = str(m.from_user.id)
        course_id = parts[1]

        try:
            stage = int(parts[2])
        except (TypeError, ValueError):
            bot.reply_to(m, "מספר שיעור לא תקין")
            return

        result = lesson_engine.complete_lesson(
            uid,
            course_id,
            stage
        )

        if result.get("already_completed"):
            bot.reply_to(m, "ℹ️ כבר השלמת את השיעור הזה")
            return

        if not result.get("ok"):
            error = result.get("error")
            if error == "course_not_started":
                message = "❌ הקורס עדיין לא התחיל. התחל דרך /academy"
            elif error == "sequential_access":
                message = "🔒 אי אפשר להשלים את השלב הזה עדיין. יש להשלים קודם את השלב הקודם."
            elif error == "course_not_found":
                message = "❌ קורס לא נמצא"
            elif error == "stage_not_found":
                message = "❌ שיעור לא נמצא"
            else:
                message = "❌ לא ניתן להשלים את השיעור הזה"
            bot.reply_to(m, message)
            return

        reward = result.get("reward", {})
        course = lesson_engine.academy_manager.get_courses().get(course_id) or {}
        total = len(course.get("stages", []))
        markup = InlineKeyboardMarkup(row_width=1)
        if stage < total:
            markup.add(
                InlineKeyboardButton(
                    f"➡️ שיעור {stage + 1}/{total}",
                    callback_data=f"slh_lesson_{course_id}_{stage + 1}"
                )
            )
        markup.add(
            InlineKeyboardButton(
                "🎓 Academy",
                callback_data="slh_academy"
            )
        )
        if stage == 1:
            bot.reply_to(
                m,
                "🎉 שיעור 1 הושלם!\n\n"
                f"⭐ נקודות: {reward.get('points', 0)}\n"
                f"💰 קרדיטים: {reward.get('credits', 0)}\n\n"
                "🔗 השלב הבא: שתף את קישור ה-Referral האישי שלך.\n"
                "אחר כך אפשר לעבור ל-Credits דרך Telegram Stars.\n\n"
                "📎 פתח /start כדי לראות את הקישור האישי.\n"
                "💎 /pay — Credits דרך Telegram Stars",
                reply_markup=markup
            )
        else:
            bot.reply_to(
                m,
                "🎉 שיעור הושלם!\n\n"
                f"⭐ נקודות: {reward.get('points', 0)}\n"
                f"💰 קרדיטים: {reward.get('credits', 0)}\n\n"
                "📊 /academy_progress",
                reply_markup=markup
            )
