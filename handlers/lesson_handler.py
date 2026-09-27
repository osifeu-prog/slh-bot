from core import academy_manager
from core import lesson_engine
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton


def _lesson_keyboard(course_id, stage, total, completed=False):
    markup = InlineKeyboardMarkup(row_width=1)
    if completed:
        markup.add(
            InlineKeyboardButton(
                "📖 פתח שוב את השיעור",
                callback_data=f"slh_lesson_{course_id}_{stage}"
            )
        )
    elif stage < total:
        markup.add(
            InlineKeyboardButton(
                f"➡️ שיעור הבא {stage + 1}/{total}",
                callback_data=f"slh_lesson_{course_id}_{stage + 1}"
            )
        )
    markup.add(
        InlineKeyboardButton(
            "📚 בחירת שיעור בקורס",
            callback_data=f"academy_{course_id}"
        )
    )
    markup.add(
        InlineKeyboardButton(
            "🎓 חזרה ל-Academy",
            callback_data="slh_academy"
        )
    )
    return markup


def register(bot):

    @bot.message_handler(commands=["lesson"])
    def lesson(m):
        parts = (m.text or "").split()
        if len(parts) != 3:
            bot.reply_to(
                m,
                "שימוש:\n/lesson bitcoin_mastery 1"
            )
            return

        uid = str(m.from_user.id)
        course_id = parts[1].strip()

        try:
            stage = int(parts[2])
        except (TypeError, ValueError):
            bot.reply_to(m, "מספר שיעור לא תקין")
            return

        course = academy_manager.get_courses().get(course_id)
        if not course:
            bot.reply_to(m, "❌ קורס לא נמצא")
            return

        if not lesson_engine.can_access_lesson(uid, course_id, stage):
            progress = academy_manager.get_course(uid, course_id) or {}
            completed = set(progress.get("completed", []) or [])
            if stage in completed:
                pass
            else:
                bot.reply_to(
                    m,
                    "🔒 השיעור נעול. יש להשלים קודם את השיעור הקודם."
                )
                return

        lesson_data = lesson_engine.get_lesson(course_id, stage)
        if not lesson_data:
            bot.reply_to(m, "❌ שיעור לא נמצא")
            return

        total = len(course.get("stages", []))
        progress = academy_manager.get_course(uid, course_id) or {}
        completed = stage in {
            int(value)
            for value in (progress.get("completed", []) or [])
            if str(value).isdigit()
        }

        bot.send_message(
            m.chat.id,
            f"📘 {lesson_data['name']}\n\n"
            f"{lesson_data['content']}\n\n"
            + ("✅ השיעור כבר הושלם — אפשר לקרוא אותו שוב בכל עת.\n"
               if completed else "סיימת? לחץ על הכפתור למטה. 👇\n"),
            reply_markup=_lesson_keyboard(
                course_id,
                stage,
                total,
                completed=completed,
            )
        )

    @bot.message_handler(commands=["finish"])
    def finish(m):
        parts = (m.text or "").split()

        if len(parts) != 3:
            bot.reply_to(
                m,
                "שימוש:\n/finish bitcoin_mastery 1"
            )
            return

        uid = str(m.from_user.id)
        course_id = parts[1].strip()

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
            course = academy_manager.get_courses().get(course_id) or {}
            total = len(course.get("stages", []))
            bot.reply_to(
                m,
                "ℹ️ כבר השלמת את השיעור הזה.\n"
                "אפשר לפתוח אותו שוב ולקרוא אותו בכל עת.",
                reply_markup=_lesson_keyboard(
                    course_id,
                    stage,
                    total,
                    completed=True,
                )
            )
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
        course = academy_manager.get_courses().get(course_id) or {}
        total = len(course.get("stages", []))

        bot.reply_to(
            m,
            "🎉 שיעור הושלם!\n\n"
            f"⭐ נקודות: {reward.get('points', 0)}\n"
            f"💰 קרדיטים: {reward.get('credits', 0)}\n\n"
            + (
                f"➡️ השיעור הבא: {stage + 1}/{total}"
                if stage < total
                else "🏁 זה היה השיעור האחרון בקורס."
            ),
            reply_markup=_lesson_keyboard(
                course_id,
                stage,
                total,
                completed=False,
            )
        )
