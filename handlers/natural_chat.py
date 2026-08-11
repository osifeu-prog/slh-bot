from handlers.llm_handler import query_llm_with_context

def register(bot, context=None):
    @bot.message_handler(
        func=lambda msg: bool(
            getattr(msg, "text", None)
        ) and not msg.text.startswith("/")
    )
    def natural_chat(msg):
        if getattr(msg.from_user, "is_bot", False):
            return

        user_text = msg.text.strip()
        if not user_text:
            return

        try:
            bot.send_chat_action(msg.chat.id, "typing")
        except Exception:
            pass

        try:
            answer = query_llm_with_context(
                user_text,
                str(msg.from_user.id)
            )
            answer = str(answer or "").strip()

            if not answer:
                answer = "⚠️ לא התקבלה תשובה מה-LLM."

        except Exception as e:
            answer = f"⚠️ שגיאה בעיבוד הבקשה: {e}"

        bot.reply_to(msg, answer[:4000])

    print("🧠 Natural Chat Router loaded")
