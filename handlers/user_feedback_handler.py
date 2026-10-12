"""User feedback handler - deterministic, no LLM."""
from future import annotations
import os
from datetime import datetime, timezone
import state_manager

OWNER_UID = os.getenv("SLH_OWNER_UID", "8789977826").strip()

CATEGORIES = [
    ("ack", ["כן", "אוקיי", "בסדר", "מאשר", "ok", "yes"]),
    ("bug", ["לא עובד", "שגיאה", "באג", "תקלה", "error", "bug", "broken", "תקוע"]),
    ("feature", ["תוסיפו", "רעיון", "הצעה", "feature", "suggestion"]),
    ("question", ["איך", "מה זה", "למה", "מתי", "?", "how", "what", "why"]),
    ("complaint", ["לא טוב", "בעיה", "גרוע", "bad"]),
]

REPLIES = {
    "ack": "✅ קיבלתי. תודה שאישרת!",
    "bug": "🐞 תודה על הדיווח! העברתי לבעלים.",
    "feature": "💡 רעיון מעניין! העברתי לבעלים.",
    "question": "❓ קיבלתי. הבעלים יענה בהקדם.",
    "complaint": "🙏 תודה על המשוב. העברתי לבעלים.",
    "general": "📩 קיבלתי את הודעתך. תודה!",
}

def _classify(text):
    low = (text or "").strip().lower()
    for cat, keywords in CATEGORIES:
        for kw in keywords:
            if kw in low:
                return cat
    return "general"

def _record(uid, username, first_name, text, category):
    def mutate(db):
        fb = db.setdefault("user_feedback", [])
        fb.append({
            "id": len(fb) + 1,
            "uid": str(uid),
            "username": username or "",
            "first_name": first_name or "",
            "text": text[:2000],
            "category": category,
            "status": "NEW",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        if len(fb) > 1000:
            del fb[:-1000]
        return {"ok": True, "id": fb[-1]["id"], "total": len(fb)}
    return state_manager.atomic_update(mutate)

def _notify_owner(bot, uid, first_name, username, text, category, fid):
    if not OWNER_UID or not OWNER_UID.isdigit():
        return
    icon = {"ack": "✅", "bug": "🐞", "feature": "💡", "question": "❓", "complaint": "🙏", "general": "📩"}.get(category, "📩")
    try:
        bot.send_message(int(OWNER_UID),
            f"{icon} משוב #{fid}\\nסוג: {category}\\nמאת: {first_name} (@{username or '-'})\\nUID: {uid}\\n----\\n{text[:800]}",
        )
    except Exception as e:
        print(f"NOTIFY_FAIL: {e}")

def register(bot):
    @bot.message_handler(func=lambda m: m.text and not m.text.startswith("/") and m.chat.type == "private", content_types=["text"])
    def handle_feedback(m):
        try:
            uid = str(m.from_user.id)
            text = (m.text or "").strip()
            if not text or uid == OWNER_UID:
                return
            category = _classify(text)
            result = _record(uid, m.from_user.username or "", m.from_user.first_name or "", text, category)
            fid = result.get("id", 0)
            try:
                bot.reply_to(m, REPLIES.get(category, REPLIES["general"]), parse_mode=None)
            except Exception as e:
                print(f"REPLY_FAIL: {e}")
            _notify_owner(bot, uid, m.from_user.first_name or "", m.from_user.username or "", text, category, fid)
        except Exception as e:
            print(f"ERROR: {e}")
    print("✅ user_feedback handler registered")
