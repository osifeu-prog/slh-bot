from core import academy_manager


def register(bot):

    @bot.message_handler(commands=['courses'])
    def courses(m):

        courses = academy_manager.get_courses()

        if not courses:
            bot.reply_to(
                m,
                "📚 אין קורסים זמינים כרע"
            )
            return

        text = "🎓 SLH Academy\n\n"

        for cid,data in courses.items():
            text += (
                f"📘 {data['title']}\n"
                f"/course_{cid}\n\n"
            )

        bot.reply_to(
            m,
            text
        )


    @bot.message_handler(commands=['progress'])
    def progress(m):

        uid=str(m.from_user.id)

        data = academy_manager.progress(uid)

        bot.reply_to(
            m,
            f"📊 ההתקדמות שלך:\n\n{data}"
        )


    @bot.message_handler(func=lambda m: m.text and m.text.startswith("/course_"))
    def start_course(m):

        uid=str(m.from_user.id)

        course_id=m.text.replace(
            "/course_",
            ""
        )

        ok=academy_manager.start_course(
            uid,
            course_id
        )

        if ok:
            bot.reply_to(
                m,
                f"✅ התחלת קורס:\n{course_id}\n\nהשתמש ב־/progress למעקב"
            )
        else:
            bot.reply_to(
                m,
                "❌ קורס לא נמצא"
            )


    @bot.message_handler(commands=['complete'])
    def complete(m):

        parts=m.text.split()

        if len(parts)!=2:
            bot.reply_to(
                m,
                "שימוש:\n/complete 1"
            )
            return

        uid=str(m.from_user.id)

        try:
            stage=int(parts[1])
        except:
            bot.reply_to(
                m,
                "מספר שלב לא תקין"
            )
            return


        result=academy_manager.complete_stage(
            uid,
            "bitcoin_mastery",
            stage
        )


        bot.reply_to(
            m,
            f"🎉 שלב הושלם!\n\n"
            f"⭐ נקודות: {result['reward']['points']}\n"
            f"💰 קרדיטים: {result['reward']['credits']}"
        )
