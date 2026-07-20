import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.ask_router import route as ask_route


def register_ask_handler(bot, context):

    @bot.message_handler(commands=['ask'])
    def ask(msg):

        question = msg.text.replace('/ask', '').strip()

        if not question:
            bot.reply_to(msg, "Usage: /ask <your question>")
            return

        local_answer = ask_route(question)

        if local_answer:
            bot.reply_to(msg, local_answer)
            return

        try:
            from handlers.llm_handler import query_llm
            answer = query_llm(question)
            bot.reply_to(msg, answer)

        except Exception as e:
            bot.reply_to(
                msg,
                f"⚠️ כל מנועי ה-AI עמוסים כרגע ({e}). נסה שוב מאוחר יותר."
            )
