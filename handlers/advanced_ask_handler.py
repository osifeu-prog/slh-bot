from handlers.llm_handler import query_llm_with_context

def register_ask_handler(bot):
    @bot.message_handler(commands=["ask"])
    def ask_cmd(msg):
        if msg.from_user and msg.from_user.is_bot:
            return

        text = msg.text or ""
        parts = text.split(maxsplit=1)
        question = parts[1].strip() if len(parts) > 1 else ""

        if not question:
            bot.reply_to(msg, "Usage: /ask [question]")
            return

        try:
            answer = query_llm_with_context(
                question,
                str(msg.from_user.id)
            )
        except Exception as e:
            answer = f"ERROR: {e}"

        bot.send_message(
            msg.chat.id,
            answer,
            parse_mode=None
        )

print("ASK MODULE LOADED FROM:", __file__)
