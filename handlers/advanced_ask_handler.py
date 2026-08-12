from handlers.llm_handler import query_llm_with_context


def _safe_clip(value, limit=3500):
    text = str(value if value is not None else "")
    text = text.replace("\x00", "").strip()

    if len(text) > limit:
        return text[:limit] + "\n...[truncated]"

    return text or "No response"


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

        question = question[:2000]

        try:
            answer = query_llm_with_context(
                question,
                str(msg.from_user.id)
            )

        except Exception:
            answer = (
                "❌ תקלה פנימית במנוע AI.\n"
                "המערכת נשמרה ללא חשיפת פרטי debug."
            )

        bot.send_message(
            msg.chat.id,
            _safe_clip(answer),
            parse_mode=None
        )


print("ASK MODULE LOADED FROM:", __file__)
