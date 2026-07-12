from core import lesson_engine


def register(bot):

    @bot.message_handler(commands=['lesson'])
    def lesson(m):

        parts = m.text.split()

        if len(parts) != 3:
            bot.reply_to(
                m,
                "שימוש:\n/lesson bitcoin_mastery 1"
            )
            return

        uid = str(m.from_user.id)

        course_id = parts[1]

        try:
            stage = int(parts[2])
        except:
            bot.reply_to(
                m,
                "מספר שיעור לא תקין"
            )
            return


        if not lesson_engine.can_access_lesson(
            uid,
            course_id,
            stage
        ):
            bot.reply_to(
                m,
                "🔒 השיעור נעול\n\n"
                "יש להשלים קודם את השיעור הקודם."
            )
            return


        lesson = lesson_engine.get_lesson(
            course_id,
            stage
        )


        if not lesson:
            bot.reply_to(
                m,
                "❌ שיעור לא נמצא"
            )
            return


        bot.reply_to(
            m,
            f"📘 {lesson['name']}\n\n"
            f"{lesson['content']}\n\n"
            f"לאחר שסיימת:\n"
            f"/finish {course_id} {stage}"
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
        except:
            bot.reply_to(
                m,
                "מספר שיעור לא תקין"
            )
            return


        result = lesson_engine.complete_lesson(
            uid,
            course_id,
            stage
        )


        if result.get("already_completed"):

            bot.reply_to(
                m,
                "ℹ️ כבר השלמת את השיעור הזה"
            )
            return


        reward = result["result"]["reward"]

        bot.reply_to(
            m,
            "🎉 שיעור הושלם!\n\n"
            f"⭐ נקודות: {reward['points']['points']}\n"
            f"💰 קרדיטים: {reward['credits']}"
        )
