from handlers.llm_handler import query_llm_with_context

def repair_hebrew(text):
    try:
        fixed = text.encode("cp1255").decode("utf-8")
        if fixed != text:
            print("ASK CP1255 REPAIRED:", fixed)
            return fixed
    except Exception as e:
        print("ASK CP1255 FAILED:", repr(e))

    return text


def register_ask_handler(bot):
    @bot.message_handler(commands=["ask"])
    def ask_cmd(msg):
        print("ASK RECEIVED:", msg.text)

        if msg.from_user and msg.from_user.is_bot:
            return

        question = (msg.text or "").replace("/ask", "", 1).strip()

        question = repair_hebrew(question)

        if not question:
            bot.reply_to(msg, "Usage: /ask [question]")
            return

        try:
            answer = query_llm_with_context(
                question,
                str(msg.from_user.id)
            )

            print("ASK QUESTION FINAL:", question)
            print("ASK ANSWER:", repr(answer))

        except Exception as e:
            answer = f"ERROR: {e}"
            print("ASK ERROR:", repr(e))

        bot.send_message(
            msg.chat.id,
            answer,
            parse_mode=None
        )


print("ASK MODULE LOADED FROM:", __file__)
