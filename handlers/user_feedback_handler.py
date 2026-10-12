"""Explicit, opt-in bug report and suggestion commands (no LLM required)."""
from __future__ import annotations

import os
from datetime import datetime, timezone

import state_manager

OWNER_UID = os.getenv("SLH_OWNER_UID", "8789977826").strip()
MAX_REPORT_LENGTH = 2000

_CATEGORIES = [
    ("bug", ["לא עובד", "שגיאה", "באג", "תקלה", "error", "bug", "broken", "תקוע"]),
    ("feature", ["תוסיפו", "רעיון", "הצעה", "feature", "suggestion", "idea"]),
    ("question", ["איך", "מה זה", "למה", "מתי", "איפה", "האם", "?", "how", "what", "why"]),
    ("complaint", ["לא טוב", "בעיה", "גרוע", "bad", "disappointed"]),
]

_REPLIES = {
    "bug": "🐞 תודה על הדיווח! שמרתי אותו והעברתי לבעלים לבדיקה.",
    "feature": "💡 תודה על ההצעה! שמרתי אותה והעברתי לבעלים לבדיקה.",
    "question": "❓ תודה. שמרתי את השאלה להעברה לבעלים.",
    "complaint": "🙏 תודה על המשוב. שמרתי אותו להעברה לבעלים.",
    "general": "📩 תודה. שמרתי את ההודעה להעברה לבעלים.",
}


def _classify(text: str) -> str:
    low = (text or "").strip().lower()
    for category, keywords in _CATEGORIES:
        if any(keyword in low for keyword in keywords):
            return category
    return "general"


def _record(uid, username, first_name, text, category) -> dict:
    safe_text = str(text or "").strip()[:MAX_REPORT_LENGTH]

    def mutate(db):
        feedback = db.setdefault("user_feedback", [])
        if not isinstance(feedback, list):
            raise ValueError("USER_FEEDBACK_STORE_INVALID")
        next_id = max(
            (int(item.get("id", 0) or 0) for item in feedback if isinstance(item, dict)),
            default=0,
        ) + 1
        entry = {
            "id": next_id,
            "uid": str(uid),
            "username": str(username or "")[:128],
            "first_name": str(first_name or "")[:128],
            "text": safe_text,
            "category": str(category),
            "status": "NEW",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        feedback.append(entry)
        if len(feedback) > 1000:
            del feedback[:-1000]
        return {"ok": True, "id": next_id, "total": len(feedback)}

    return state_manager.atomic_update(mutate)


def _notify_owner(bot, uid, first_name, username, text, category, feedback_id):
    owner_uid = OWNER_UID
    if not owner_uid or not owner_uid.isdigit() or str(uid) == owner_uid:
        return
    icon = {"bug": "🐞", "feature": "💡", "question": "❓", "complaint": "🙏"}.get(category, "📩")
    body = (
        f"{icon} דיווח חדש #{feedback_id}\n"
        f"סוג: {category}\n"
        f"מאת: {str(first_name or 'משתמש')[:128]} (@{str(username or '—')[:128]})\n"
        f"UID: {uid}\n"
        "──────────\n"
        f"{str(text or '')[:800]}"
    )
    try:
        bot.send_message(int(owner_uid), body)
    except Exception as exc:
        # Persisted feedback is the source of truth even if the alert cannot be delivered.
        print(f"USER_FEEDBACK_NOTIFY_FAIL: {type(exc).__name__}")


def register(bot):
    """Register explicit commands only; ordinary conversation remains available to AI handlers."""
    @bot.message_handler(commands=["bugreport", "suggest"], content_types=["text"])
    def handle_feedback(message):
        try:
            raw = str(getattr(message, "text", "") or "").strip()
            command, _, body = raw.partition(" ")
            command = command.split("@", 1)[0].lower().lstrip("/")
            report = body.strip()[:MAX_REPORT_LENGTH]
            if not report:
                command_example = "/suggest" if command == "suggest" else "/bugreport"
                bot.reply_to(
                    message,
                    f"📝 הוסף פרטים אחרי הפקודה. לדוגמה: {command_example} הכפתור לא עובד",
                    parse_mode=None,
                )
                return

            user = getattr(message, "from_user", None)
            uid = str(getattr(user, "id", "") or "")
            if not uid.isdigit():
                bot.reply_to(message, "⛔ לא הצלחתי לאמת את חשבון Telegram. לא נשמר דיווח.", parse_mode=None)
                return
            username = str(getattr(user, "username", "") or "")
            first_name = str(getattr(user, "first_name", "") or "")
            category = "feature" if command == "suggest" else "bug"
            result = _record(uid, username, first_name, report, category)
            feedback_id = result.get("id", 0)
            bot.reply_to(
                message,
                f"{_REPLIES[category]}\nמספר דיווח: #{feedback_id}",
                parse_mode=None,
            )
            _notify_owner(bot, uid, first_name, username, report, category, feedback_id)
        except Exception as exc:
            print(f"USER_FEEDBACK_HANDLER_ERROR: {type(exc).__name__}")
            try:
                bot.reply_to(message, "⛔ לא הצלחתי לשמור את הדיווח. נסה שוב מאוחר יותר.", parse_mode=None)
            except Exception:
                pass

    print("✅ opt-in bugreport/suggest handler registered")
