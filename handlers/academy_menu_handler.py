from core import academy_manager
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton


def _lesson_keyboard(course_id, stage):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton(
            "📖 פתח שיעור",
            callback_data=f"slh_lesson_{course_id}_{stage}"
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

    @bot.message_handler(commands=['academy'])
    def academy(m):
        _send_academy(bot, m.chat.id, str(m.from_user.id))

    @bot.callback_query_handler(func=lambda c: c.data == "slh_academy")
    def academy_callback(call):
        bot.answer_callback_query(call.id)
        _send_academy(bot, call.message.chat.id, str(call.from_user.id))

    @bot.callback_query_handler(
        func=lambda c: c.data.startswith("academy_")
    )
    def academy_course(call):
        uid = str(call.from_user.id)
        cid = call.data.replace("academy_", "", 1)
        course = academy_manager.get_courses().get(cid)

        if not course:
            bot.answer_callback_query(call.id, "קורס לא נמצא")
            return

        # Starting an already-started course is idempotent and preserves progress.
        academy_manager.start_course(uid, cid)
        progress = academy_manager.get_course(uid, cid)
        current = int(progress.get("stage", 0) or 0) + 1
        total = len(course.get("stages", []))
        if total:
            current = min(current, total)

        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            f"📘 {course['title']}\n\n"
            f"השיעור הבא שלך: שלב {current}\n\n"
            "לחץ על הכפתור כדי לפתוח את השיעור.",
            reply_markup=_lesson_keyboard(cid, current)
        )

    @bot.callback_query_handler(
        func=lambda c: c.data.startswith("slh_lesson_")
    )
    def open_lesson(call):
        parts = call.data.split("_")
        if len(parts) != 4:
            bot.answer_callback_query(call.id, "שיעור לא תקין")
            return

        _, _, course_id, stage_raw = parts
        try:
            stage = int(stage_raw)
        except ValueError:
            bot.answer_callback_query(call.id, "שיעור לא תקין")
            return

        from core import lesson_engine
        uid = str(call.from_user.id)
        if not lesson_engine.can_access_lesson(uid, course_id, stage):
            bot.answer_callback_query(call.id, "השיעור נעול")
            return

        lesson = lesson_engine.get_lesson(course_id, stage)
        if not lesson:
            bot.answer_callback_query(call.id, "שיעור לא נמצא")
            return

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
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            f"📘 {lesson['name']}\n\n{lesson['content']}",
            reply_markup=markup
        )

    @bot.callback_query_handler(
        func=lambda c: c.data.startswith("slh_finish_")
    )
    def finish_lesson_callback(call):
        parts = call.data.split("_")
        if len(parts) != 4:
            bot.answer_callback_query(call.id, "שיעור לא תקין")
            return

        _, _, course_id, stage_raw = parts
        try:
            stage = int(stage_raw)
        except ValueError:
            bot.answer_callback_query(call.id, "שיעור לא תקין")
            return

        from core import lesson_engine
        uid = str(call.from_user.id)
        result = lesson_engine.complete_lesson(uid, course_id, stage)

        if result.get("already_completed"):
            bot.answer_callback_query(call.id, "השיעור כבר הושלם")
            return
        if not result.get("ok"):
            bot.answer_callback_query(call.id, "לא ניתן להשלים את השיעור")
            return

        reward = result.get("reward", {})
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton(
                "🎓 המשך ל-Academy",
                callback_data="slh_academy"
            )
        )
        markup.add(
            InlineKeyboardButton(
                "💎 Credits",
                callback_data="slh_credits"
            )
        )

        bot.answer_callback_query(call.id, "השיעור הושלם ✓")
        bot.send_message(
            call.message.chat.id,
            "🎉 השיעור הושלם!\n\n"
            f"⭐ נקודות: {reward.get('points', 0)}\n"
            f"💰 קרדיטים: {reward.get('credits', 0)}\n\n"
            "בחר את הצעד הבא:",
            reply_markup=markup
        )


def _send_academy(bot, chat_id, uid):
    courses = academy_manager.get_courses()
    if not courses:
        bot.send_message(chat_id, "📚 אין קורסים זמינים")
        return

    text = "🎓 SLH ACADEMY\n\nמערכת הלימוד שלך:\n\n"
    markup = InlineKeyboardMarkup(row_width=1)

    for cid, data in courses.items():
        progress = academy_manager.get_course(uid, cid)
        stage = progress.get("stage", 0)
        text += (
            f"📘 {data['title']}\n"
            f"התקדמות: {stage}/{len(data['stages'])}\n\n"
        )
        markup.add(
            InlineKeyboardButton(
                f"📖 {data['title']}",
                callback_data=f"academy_{cid}"
            )
        )

    bot.send_message(chat_id, text, reply_markup=markup)
