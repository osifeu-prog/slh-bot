from handlers.llm_handler import query_llm_with_context

def repair_hebrew(text):
    """׳ ׳¡׳™׳•׳ ׳׳©׳—׳–׳¨ ׳˜׳§׳¡׳˜ ׳©׳§׳•׳“׳“ ׳׳ ׳ ׳›׳•׳ ׳‘׳׳¢׳‘׳¨"""
    try:
        # ׳ ׳™׳¡׳™׳•׳ cp1255 -> utf8
        fixed = text.encode("cp1255", errors="ignore").decode("utf-8", errors="ignore")
        if fixed != text and any('ײ' <= c <= '׳×' for c in fixed):
            print("ASK CP1255 REPAIRED")
            return fixed
    except:
        pass
    try:
        # ׳ ׳™׳¡׳™׳•׳ iso-8859-8 -> utf8
        fixed = text.encode("iso-8859-8", errors="ignore").decode("utf-8", errors="ignore")
        if fixed != text and any('ײ' <= c <= '׳×' for c in fixed):
            print("ASK ISO-8859-8 REPAIRED")
            return fixed
    except:
        pass
    try:
        # ׳×׳™׳§׳•׳ ׳ ׳₪׳•׳¥: bytes ׳’׳•׳׳׳™׳™׳ ׳©׳”׳×׳₪׳¢׳ ׳—׳• ׳›ג€‘latin1
        fixed = text.encode("latin1", errors="ignore").decode("utf-8", errors="ignore")
        if fixed != text:
            print("ASK LATIN1 REPAIRED")
            return fixed
    except:
        pass
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

