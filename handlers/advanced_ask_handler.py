from handlers.llm_handler import query_llm_with_context
from core.ask_router import route
from core.keyboard_detector import normalize_keyboard_text
from core.authority import is_owner, get_role


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
        question = normalize_keyboard_text(parts[1].strip()) if len(parts) > 1 else ""

        if not question:
            bot.reply_to(msg, "Usage: /ask [question]")
            return

        uid = str(msg.from_user.id)
        question = question[:2000]

        # Raw exec output may contain secrets, paths, diagnostics, or other users' data.
        # It is never passed to AI for non-owners.
        if is_owner(uid):
            try:
                import json
                from pathlib import Path

                db_path = Path("state/db.json")
                db = json.loads(db_path.read_text(encoding="utf-8"))
                last_exec = db.get("last_exec_output")

                if last_exec:
                    question = (
                        question
                        + "\n\n[LAST_EXEC_COMMAND]\n"
                        + last_exec.get("command", "")
                        + "\n\n[LAST_EXEC_OUTPUT]\n"
                        + last_exec.get("output", "")[:2500]
                    )
            except Exception:
                pass

        try:
            answer = route(question, uid)
            if not answer:
                raise ValueError("no route answer")
        except Exception:
            answer = query_llm_with_context(
                question,
                uid
            )
        if not answer:
            answer = "⚠️ אין תשובה זמינה כרגע."

        bot.send_message(
            msg.chat.id,
            _safe_clip(answer),
            parse_mode=None
        )


print("ASK MODULE LOADED FROM:", __file__)
