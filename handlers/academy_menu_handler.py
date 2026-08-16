from core import academy_manager
from core import profile_manager
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton


def register(bot):

    @bot.message_handler(commands=['academy'])
    def academy(m):

        uid = str(m.from_user.id)

        courses = academy_manager.get_courses()

        if not courses:
            bot.reply_to(
                m,
                "📚 אין קורסים זמינים"
            )
            return


        text = (
            "🎓 SLH ACADEMY\n\n"
            "מערכת הלימוד שלך:\n\n"
        )

        markup = InlineKeyboardMarkup()


        for cid,data in courses.items():

            progress = (
                academy_manager
                .get_course(
                    uid,
                    cid
                )
            )

            stage = progress.get(
                "stage",
                0
            )

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


        bot.send_message(
            m.chat.id,
            text,
            reply_markup=markup
        )


    @bot.callback_query_handler(
        func=lambda c: c.data.startswith("academy_")
    )
    def academy_course(call):

        uid = str(call.from_user.id)

        cid = call.data.replace(
            "academy_",
            ""
        )


        course = academy_manager.get_courses().get(cid)

        if not course:
            bot.answer_callback_query(
                call.id,
                "קורס לא נמצא"
            )
            return


        progress = academy_manager.get_course(
            uid,
            cid
        )

        current = progress.get(
            "stage",
            0
        ) + 1


        if current > len(course["stages"]):
            current = len(course["stages"])


        text = (
            f"📘 {course['title']}\n\n"
            f"השיעור הבא שלך:\n"
            f"שלב {current}\n\n"
            f"/lesson {cid} {current}"
        )


        bot.send_message(
            call.message.chat.id,
            text
        )
