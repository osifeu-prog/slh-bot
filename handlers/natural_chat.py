from handlers.llm_handler import query_llm_with_context
from core.keyboard_detector import normalize_keyboard_text

def register(bot, context=None):
    @bot.message_handler(
        func=lambda msg: bool(
            getattr(msg, "text", None)
        ) and not msg.text.startswith("/")
    )
    def natural_chat(msg):
        if getattr(msg.from_user, "is_bot", False):
            return

        user_text = normalize_keyboard_text(msg.text.strip())
        if not user_text:
            return

        try:
            bot.send_chat_action(msg.chat.id, "typing")
        except Exception:
            pass

        try:
            answer = query_llm_with_context(
                user_text,
                str(msg.from_user.id),
                skip_checks=True
            )
            answer = str(answer or "").strip()

            if not answer:
                answer = "LLM returned no answer."

        except Exception as e:
            answer = f"LLM error: {e}"

        try:
            bot.send_message(msg.chat.id, answer[:4000])
        except Exception as e:
            print("NATURAL CHAT SEND ERROR:", e)

print("Natural Chat Router loaded")
