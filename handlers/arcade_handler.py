from core import arcade_engine


def _uid(msg):
    return str(msg.from_user.id)


def register(bot):
    @bot.message_handler(commands=["arcade"])
    def arcade(msg):
        result = arcade_engine.start_game(_uid(msg))
        status = result.get("status")

        if status == "insufficient_credits":
            bot.reply_to(msg, "🎮 Arcade עולה 5 Credits. אין לך כרגע מספיק Credits.")
            return

        if status == "already_active":
            bot.reply_to(
                msg,
                "🎮 המשחק כבר פעיל.\n"
                f"ענה על: {result['question'] if 'question' in result else 'השאלה הנוכחית'}",
            )
            return

        bot.reply_to(
            msg,
            "🎮 *SLH Arcade*\n\n"
            "כניסה: 5 Credits · זמן: 60 שניות\n"
            f"{result['question']}\n\n"
            "שלח רק את התשובה המספרית.\n"
            "עצירה: /arcade_stop",
            parse_mode="Markdown",
        )

    @bot.message_handler(commands=["arcade_stop"])
    def arcade_stop(msg):
        result = arcade_engine.finish_game(_uid(msg))
        if result.get("status") == "already_finished":
            bot.reply_to(msg, "ℹ️ אין משחק Arcade פעיל.")
            return
        bot.reply_to(
            msg,
            f"🏁 המשחק הסתיים.\nניקוד: {result['score']}\n⭐ Points: +{result['points']}",
        )

    @bot.message_handler(
        func=lambda msg: (
            bool(getattr(msg, "text", None))
            and not msg.text.startswith("/")
            and _uid(msg) in arcade_engine.ACTIVE
        )
    )
    def arcade_answer(msg):
        result = arcade_engine.answer_game(_uid(msg), msg.text)
        status = result.get("status")

        if status == "answered":
            verdict = "✅ נכון" if result["correct"] else "❌ לא נכון"
            bot.reply_to(
                msg,
                f"{verdict} · ניקוד: {result['score']}\n\n{result['question']}",
            )
            return

        if status == "finished":
            bot.reply_to(
                msg,
                f"⏱️ הזמן נגמר.\nניקוד: {result['score']}\n⭐ Points: +{result['points']}",
            )
            return

        bot.reply_to(msg, "ℹ️ אין משחק Arcade פעיל.")

    print("arcade_handler loaded")
