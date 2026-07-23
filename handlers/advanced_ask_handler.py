from handlers.llm_handler import query_llm_with_context
def register_ask_handler(bot):
    @bot.message_handler(commands=['ask'])
    def ask(msg):
        q = msg.text.replace('/ask','').strip()
        if not q: 
            return bot.reply_to(msg, "Usage: /ask <שאלה>")
        uid = str(msg.from_user.id)
        try:
            ans = query_llm_with_context(q, uid)
        except Exception as e:
            ans = "שגיאה ב-LLM: " + str(e)
        bot.reply_to(msg, ans)
