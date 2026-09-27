from core.ask_router import route
from core.keyboard_detector import normalize_keyboard_text
from core.conversation_memory import record_turn


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

        # Do not spend LLM quota on technical identifiers accidentally pasted
        # into chat. Give a deterministic instruction instead.
        compact = user_text.strip()
        if (compact.startswith(("UQ", "EQ")) and len(compact) >= 40):
            bot.send_message(
                msg.chat.id,
                "📌 זוהתה כתובת TON.\n"
                "לבדיקת הפקדה צריך TX hash, לא כתובת.\n"
                "אם מדובר ב-USDT/Jetton: המסלול הזה עדיין אינו נתמך ל-Credits."
            )
            return

        if (len(compact) == 42 and compact.startswith(("0x", "0X"))):
            bot.send_message(
                msg.chat.id,
                "📌 זוהתה כתובת BNB/BSC.\n"
                "כתובת אינה TX hash ולא מבצעת זיכוי.\n"
                "הפקדת BNB נבדקת רק דרך /claim <TX hash> לאחר שהמסלול פתוח."
            )
            return

        if (len(compact) == 64 and all(c in "0123456789abcdefABCDEF" for c in compact)):
            bot.send_message(
                msg.chat.id,
                "📌 התקבל מזהה באורך 64 תווים.\n"
                "אם זה TX hash, השתמש בפקודה המתאימה למסלול הנכס; אל תשלח כספים נוספים לצורך בדיקה."
            )
            return

        if compact.upper().startswith("SLH") and compact[3:].isdigit():
            bot.send_message(
                msg.chat.id,
                "📌 זהו Memo של SLH. ה-Memo לבדו אינו הפקדה ואינו מזכה Credits.\n"
                "יש לצרף אותו להעברת TON native אל Treasury לפי ההוראות."
            )
            return

        try:
            bot.send_chat_action(msg.chat.id, "typing")
        except Exception:
            pass

        try:
            answer = route(
                user_text,
                str(msg.from_user.id)
            )

            answer = str(answer or "").strip()

            if not answer:
                answer = "לא התקבלה תשובה כרגע."

        except Exception as e:
            print("NATURAL CHAT ROUTE ERROR:", e)
            answer = "שגיאה בעיבוד הבקשה."

        try:
            bot.send_message(
                msg.chat.id,
                answer[:4000],
                parse_mode=None
            )
            if (
                answer
                and not answer.startswith("🧠 ה־AI אינו זמין כרגע")
                and not answer.startswith("מנוע ה-AI לא זמין כרגע")
            ):
                record_turn(
                    str(msg.from_user.id),
                    user_text,
                    answer[:4000],
                )
        except Exception as e:
            print("NATURAL CHAT SEND ERROR:", e)


print("Natural Chat Router loaded → unified ASK route")
