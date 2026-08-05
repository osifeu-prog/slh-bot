from handlers.llm_handler import query_llm_with_context

def register_ask_handler(bot):
    @bot.message_handler(commands=["ask"])
    def ask_cmd(msg):
        if msg.from_user and msg.from_user.is_bot:
            return
        question = (msg.text or "").replace("/ask", "", 1).strip()
        if not question:
            bot.reply_to(msg, "Usage: /ask [question]")
            return
        try:
            answer = query_llm_with_context(question, str(msg.from_user.id))
        except Exception as e:
            answer = f"שגיאה: {e}"
        bot.reply_to(msg, answer)
