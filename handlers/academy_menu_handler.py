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


def _completed_course(progress, total):
    completed = {int(x) for x in progress.get("completed", [])}
    return total > 0 and len(completed) >= total and all(
        stage in completed for stage in range(1, total + 1)
    )


def _next_stage(progress, total):
    completed = {int(x) for x in progress.get("completed", [])}
    for stage in range(1, total + 1):
        if stage not in completed:
            return stage
    return None


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

        academy_manager.start_course(uid, cid)
        progress = academy_manager.get_course(uid, cid)
        current = int(progress.get("stage", 0) or 0)
        total = len(course.get("stages", []))
        next_stage = _next_stage(progress, total)

        bot.answer_callback_query(call.id)

        if _completed_course(progress, total):
            bot.send_message(
                call.message.chat.id,
                f"🎓 {course['title']}\n\n"
                "✅ הקורס הושלם במלואו!\n\n"
                "כל נקודות הלימוד נזקפו לחשבונך. אפשר להמשיך לקורס הבא.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(
                    "🎓 חזרה ל-Academy", callback_data="slh_academy"
                )]])
            )
            return

        if next_stage is None:
            next_stage = min(current + 1, total) if total else 1

        bot.send_message(
            call.message.chat.id,
            f"📘 {course['title']}\n\n"
            f"השיעור הבא שלך: שלב {next_stage}\n\n"
            "לחץ על הכפתור כדי לפתוח את השיעור.",
            reply_markup=_lesson_keyboard(cid, next_stage)
        )

    @bot.callback_query_handler(
        func=lambda c: c.data.startswith("slh_lesson_")
    )
    def open_lesson(call):
        raw = call.data[len("slh_lesson_"):]
        if "_" not in raw:
            bot.answer_callback_query(call.id, "שיעור לא תקין")
            if call.message:
                bot.send_message(
                    call.message.chat.id,
                    "⚠️ כפתור השיעור הזה ישן או לא תקין. חזור ל-Academy ופתח את השיעור מחדש."
                )
            return

        course_id, stage_raw = raw.rsplit("_", 1)
        try:
            stage = int(stage_raw)
        except ValueError:
            bot.answer_callback_query(call.id, "שיעור לא תקין")
            if call.message:
                bot.send_message(
                    call.message.chat.id,
                    "⚠️ כפתור השיעור הזה ישן או לא תקין. חזור ל-Academy ופתח את השיעור מחדש."
                )
            return

        from core import lesson_engine
        uid = str(call.from_user.id)
        if not lesson_engine.can_access_lesson(uid, course_id, stage):
            bot.answer_callback_query(call.id, "השיעור נעול")
            if call.message:
                bot.send_message(
                    call.message.chat.id,
                    "🔒 השיעור עדיין נעול. חזור ל-Academy והמשך מהשלב הבא שלך."
                )
            return

        lesson = lesson_engine.get_lesson(course_id, stage)
        if not lesson:
            bot.answer_callback_query(call.id, "השיעור לא נמצא")
            if call.message:
                bot.send_message(
                    call.message.chat.id,
                    "❌ תוכן השיעור לא נמצא כרגע. חזור ל-Academy ונסה שוב."
                )
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
        raw = call.data[len("slh_finish_"):]
        if "_" not in raw:
            bot.answer_callback_query(call.id, "שיעור לא תקין")
            return
        course_id, stage_raw = raw.rsplit("_", 1)
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
        course_reward = result.get("course_reward", {})
        lesson_points = int(reward.get("points", 0) or 0)
        course_points = int(course_reward.get("points", 0) or 0)

        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton(
                "🎓 המשך ל-Academy",
                callback_data="slh_academy"
            )
        )

        bot.answer_callback_query(call.id, "השיעור הושלם ✓")
        completion_text = (
            "🎉 השיעור הושלם!\n\n"
            f"⭐ נקודות שיעור: {lesson_points}\n"
        )
        if course_points:
            completion_text += (
                f"🏆 בונוס סיום קורס: {course_points} נקודות\n"
            )
        completion_text += (
            "\nהנקודות נזקפו לחשבונך. חזור ל-Academy כדי לפתוח את השלב הבא."
        )
        bot.send_message(
            call.message.chat.id,
            completion_text,
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
        stage = int(progress.get("stage", 0) or 0)
        completed = {int(x) for x in progress.get("completed", [])}
        total = len(data.get("stages", []))
        status = " ✅ הושלם" if _completed_course(progress, total) else ""
        text += (
            f"📘 {data['title']}\n"
            f"התקדמות: {len(completed)}/{total}{status}\n\n"
        )
        markup.add(
            InlineKeyboardButton(
                f"📖 {data['title']}", callback_data=f"academy_{cid}"
            )
        )

    bot.send_message(chat_id, text, reply_markup=markup)
