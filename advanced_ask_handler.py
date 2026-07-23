import json
from handlers.llm_handler import query_llm_with_context

def register_ask_handler(bot):
    @bot.message_handler(commands=['ask'])
    def ask(msg):
        question = msg.text.replace('/ask','').strip()
        if not question:
            bot.reply_to(msg, "Usage: /ask <שאלה>")
            return
        user_id = str(msg.from_user.id)
        try:
            answer = query_llm_with_context(question, user_id)
        except Exception as e:
            answer = f"שיאה: {e}"
        bot.reply_to(msg, answer)
