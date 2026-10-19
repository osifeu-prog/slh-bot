from core import academy_manager
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton


def _lesson_picker(course_id, stages, completed):
    markup = InlineKeyboardMarkup(row_width=2)
    completed = set(int(x) for x in (completed or []) if str(x).isdigit())

    for item in stages:
        stage_id = int(item.get("id"))
        if stage_id in completed:
            label = f"✅ שיעור {stage_id}"
        elif stage_id == (max(completed) + 1 if completed else 1):
            label = f"▶️ המשך {stage_id}"
        else:
            label = f"🔒 שיעור {stage_id}"

        markup.add(
            InlineKeyboardButton(
                label,
                callback_data=f"slh_lesson_{course_id}_{stage_id}"
            )
        )

    markup.add(
        InlineKeyboardButton(
            "🎓 חזרה ל-Academy",
            callback_data="slh_academy"
        )
    )
    return markup


def _course_overview(bot, chat_id, uid, course_id):
    course = academy_manager.get_courses().get(course_id)
    if not course:
        bot.send_message(chat_id, "❌ קורס לא נמצא")
        return

    progress = academy_manager.get_course(uid, course_id) or {}
    completed = set(
        int(x) for x in (progress.get("completed", []) or [])
        if str(x).isdigit()
    )
    stages = course.get("stages", [])
    total = len(stages)
    complete = bool(total and len(completed) >= total)

    if complete:
        intro = (
            f"🎓 {course['title']}\n\n"
            "✅ הקורס הושלם במלואו.\n"
            "אפשר לחזור לכל שיעור, לקרוא אותו שוב ולהמשיך מהנקודה הרצויה.\n\n"
            "בחר שיעור:"
        )
    else:
        next_stage = min(
            [int(item.get("id")) for item in stages
             if int(item.get("id")) not in completed],
            default=1,
        )
        intro = (
            f"🎓 {course['title']}\n\n"
            f"▶️ ההמשך שלך: שיעור {next_stage}/{total}\n"
            "שיעורים שהושלמו נשארים פתוחים לחזרה בכל עת.\n\n"
            "בחר שיעור:"
        )

    bot.send_message(
        chat_id,
        intro,
        reply_markup=_lesson_picker(course_id, stages, completed),
    )


def register(bot):

    @bot.message_handler(commands=["academy"])
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

        from handlers.academy_handler import _paid_course_lock
        locked = _paid_course_lock(uid, cid)
        if locked:
            bot.answer_callback_query(call.id, "🔒 הקורס בתשלום")
            bot.send_message(call.message.chat.id, locked)
            return

        academy_manager.start_course(uid, cid)
        bot.answer_callback_query(call.id)
        _course_overview(bot, call.message.chat.id, uid, cid)

    @bot.callback_query_handler(
        func=lambda c: c.data.startswith("slh_lesson_")
    )
    def open_lesson(call):
        raw = call.data[len("slh_lesson_"):]
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

        if not lesson_engine.can_access_lesson(uid, course_id, stage):
            if not lesson_engine.has_course_access(uid, course_id):
                from handlers.academy_handler import _paid_course_lock
                locked = _paid_course_lock(uid, course_id)
                bot.answer_callback_query(call.id, "🔒 הקורס בתשלום")
                bot.send_message(
                    call.message.chat.id,
                    locked or "🔒 אין לך הרשאה לקורס הזה."
                )
            else:
                bot.answer_callback_query(
                    call.id,
                    "🔒 יש להשלים קודם את השיעור הקודם",
                    show_alert=False,
                )
            return

        lesson = lesson_engine.get_lesson(course_id, stage)
        if not lesson:
            bot.answer_callback_query(call.id, "השיעור לא נמצא")
            return

        progress = academy_manager.get_course(uid, course_id) or {}
        completed = stage in {
            int(x) for x in (progress.get("completed", []) or [])
            if str(x).isdigit()
        }
        course = academy_manager.get_courses().get(course_id) or {}
        total = len(course.get("stages", []))

        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton(
                "✅ כבר הושלם — קרא שוב",
                callback_data=f"slh_lesson_{course_id}_{stage}"
            )
            if completed else
            InlineKeyboardButton(
                "✅ סיימתי את השיעור",
                callback_data=f"slh_finish_{course_id}_{stage}"
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

        bot.answer_callback_query(call.id)
        from handlers.lesson_handler import _split_message
        message_text = (
            f"📘 {lesson['name']}\n\n{lesson['content']}\n\n"
            + (
                "✅ השיעור כבר הושלם — ניתן לחזור אליו בכל עת."
                if completed else
                "סיימת? לחץ על הכפתור למטה. 👇"
            )
        )
        chunks = _split_message(message_text)
        for index, chunk in enumerate(chunks):
            if index == len(chunks) - 1:
                bot.send_message(
                    call.message.chat.id,
                    chunk,
                    reply_markup=markup,
                )
            else:
                bot.send_message(call.message.chat.id, chunk)

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
            bot.send_message(
                call.message.chat.id,
                "ℹ️ השיעור כבר הושלם. אפשר לפתוח אותו שוב דרך בחירת השיעור.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        "📚 בחירת שיעור בקורס",
                        callback_data=f"academy_{course_id}"
                    )
                ]]),
            )
            return

        if not result.get("ok"):
            if result.get("error") == "course_locked":
                from handlers.academy_handler import _paid_course_lock
                locked = _paid_course_lock(uid, course_id)
                bot.answer_callback_query(call.id, "🔒 הקורס בתשלום")
                bot.send_message(
                    call.message.chat.id,
                    locked or "🔒 אין לך הרשאה לקורס הזה."
                )
            else:
                bot.answer_callback_query(call.id, "לא ניתן להשלים את השיעור")
            return

        reward = result.get("reward", {})
        course = academy_manager.get_courses().get(course_id) or {}
        total = len(course.get("stages", []))
        markup = InlineKeyboardMarkup(row_width=1)

        if stage < total:
            markup.add(
                InlineKeyboardButton(
                    f"➡️ שיעור {stage + 1}/{total}",
                    callback_data=f"slh_lesson_{course_id}_{stage + 1}"
                )
            )
        else:
            markup.add(
                InlineKeyboardButton(
                    "🏁 הקורס הושלם — פתח את רשימת השיעורים",
                    callback_data=f"academy_{course_id}"
                )
            )

        markup.add(
            InlineKeyboardButton(
                "🎓 Academy",
                callback_data="slh_academy"
            )
        )

        bot.answer_callback_query(call.id, "השיעור הושלם ✓")
        next_text = (
            f"➡️ השיעור הבא: {stage + 1}/{total}"
            if stage < total else
            "🏁 זה היה השיעור האחרון. כל השיעורים נשארים זמינים לחזרה."
        )
        bot.send_message(
            call.message.chat.id,
            "🎉 השיעור הושלם!\n\n"
            f"⭐ נקודות: {reward.get('points', 0)}\n\n"
            f"{next_text}",
            reply_markup=markup
        )


def _button_course_title(course_id, title):
    """Keep Telegram inline button labels short while preserving full titles in the menu."""
    short = {
        "music_reading_basics": "קריאת תווים וקצב",
        "music_theory_foundations": "תאוריה מוזיקלית",
        "harmony_voice_leading": "הרמוניה והובלת קולות",
        "voice_and_ear_training": "קול ושמיעה",
        "bitcoin_mastery": "ביטקוין מאסטרי",
        "ethereum": "אתריום מאסטרי",
        "slh_vs_eth_sol": "SLH מול ETH/SOL",
        "ai_tokens": "טוקנים ו-AI",
        "governance_game_theory": "ממשל ותורת המשחקים",
        "algo_trading_999": "מסחר אלגוריתמי",
    }
    value = short.get(course_id, str(title or course_id))
    return value if len(value) <= 32 else value[:31] + "…"


def _course_category(course_id):
    if course_id in {
        "music_reading_basics", "music_theory_foundations",
        "harmony_voice_leading", "voice_and_ear_training",
    }:
        return "🎼 מוזיקה, תאוריה וקול"
    if course_id == "algo_trading_999":
        return "📈 מסחר וניתוח שוק"
    return "🧠 ידע דיגיטלי וכלכלה"


def _send_academy(bot, chat_id, uid):
    courses = academy_manager.get_courses()
    if not courses:
        bot.send_message(chat_id, "📚 אין קורסים זמינים")
        return

    music_first = [
        "music_reading_basics", "music_theory_foundations",
        "harmony_voice_leading", "voice_and_ear_training",
    ]
    trading_last = ["algo_trading_999"]
    ordered_ids = (
        [cid for cid in music_first if cid in courses]
        + [cid for cid in courses if cid not in music_first + trading_last]
        + [cid for cid in trading_last if cid in courses]
    )

    text = "🎓 SLH ACADEMY\n\nבחר מסלול לימוד. ההתקדמות נשמרת, ואפשר לחזור לשיעורים שהושלמו.\n"
    markup = InlineKeyboardMarkup(row_width=1)
    current_category = None

    for cid in ordered_ids:
        data = courses[cid]
        category = _course_category(cid)
        if category != current_category:
            current_category = category
            text += "\n" + category + "\n"
        
        stages = data.get("stages", [])
        total = len(stages)
        progress = academy_manager.get_course(uid, cid) or {}

        completed = set()
        for value in progress.get("completed", []) or []:
            try:
                completed.add(int(value))
            except (TypeError, ValueError):
                pass

        remaining = []
        for item in stages:
            try:
                stage_id = int(item.get("id"))
            except (TypeError, ValueError):
                continue
            if stage_id not in completed:
                remaining.append(stage_id)

        short_title = _button_course_title(cid, data.get("title", cid))
        text += f"📘 {data['title']}\n"

        if total and not remaining:
            text += (
                f"✅ הושלם: {total}/{total} · אפשר לחזור בכל עת.\n\n"
            )
            button_text = f"📖 חזרה · {short_title}"
        else:
            next_stage = remaining[0] if remaining else min(len(completed) + 1, total)
            text += f"▶️ ההמשך שלך: שיעור {next_stage}/{total}\n\n"
            button_text = f"▶️ {short_title} · {next_stage}/{total}"

        markup.add(
            InlineKeyboardButton(
                button_text,
                callback_data=f"academy_{cid}"
            )
        )

    bot.send_message(chat_id, text, reply_markup=markup)
