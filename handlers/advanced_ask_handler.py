from handlers.llm_handler import query_llm_with_context

def register_ask_handler(bot):
    @bot.message_handler(commands=["ask"])
    def ask_cmd(msg):
        print("ASK RECEIVED ASCII:", ascii(msg.text))

        if msg.from_user and msg.from_user.is_bot:
            return

        text = msg.text or ""
        question = text.split(maxsplit=1)[1].strip() if len(text.split(maxsplit=1)) > 1 else ""

        print("ASK QUESTION ASCII:", ascii(question))
        print("ASK QUESTION UNICODE_ESCAPE:", question.encode("unicode_escape").decode("ascii"))
        print("ASK QUESTION CODEPOINTS:", ",".join(f"U+{ord(c):04X}" for c in question))

        if not question:
            bot.reply_to(msg, "Usage: /ask [question]")
            return

        try:
            answer = query_llm_with_context(
                question,
                str(msg.from_user.id)
            )

            print("ASK ANSWER ASCII:", ascii(answer))

        except Exception as e:
            answer = f"ERROR: {e}"
            print("ASK ERROR ASCII:", ascii(str(e)))

        bot.send_message(
            msg.chat.id,
            answer,
            parse_mode=None
        )

print("ASK MODULE LOADED FROM:", __file__)
