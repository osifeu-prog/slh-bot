import os
import json
from pathlib import Path

from core.ask_guard import guard, guarded_message
from core.ai_guard import provider_available
from handlers.llm_handler import query_llm_with_context


def local_answer(question, user_id):
    """
    Local answers only.
    No LLM/API call.
    Returns:
        str  -> local answer
        None -> unknown question, may continue to LLM
    """

    q = question.strip().lower()

    # System architecture / ASK Router diagnostics
    if (
        "ask router" in q
        or "מערכת ה-ask" in q
        or "מערכת ask" in q
        or "circuit breaker" in q
        or "429" in q
        or "כפילויות" in q
        or "הגנה" in q and "llm" in q
    ):
        return (
            "🧠 ASK ROUTER STATUS\n\n"
            "✅ /ask פעיל דרך advanced_ask_handler\n"
            "✅ הגנת Duplicate/Cooldown קיימת\n"
            "⚠️ מסלול ה-LLM דורש חיבור מלא ל-AI Guard\n"
            "⚠️ ה-Router הישן דורש ניקוי קידוד וחיבור מסודר\n"
            "🛡️ הבדיקה בוצעה מקומית — ללא שליחת מידע ל-LLM."
        )

    # Agent count
    if "כמה סוכנים" in q or "מספר הסוכנים" in q:
        try:
            with open("state/db.json", encoding="utf-8") as f:
                db = json.load(f)

            agents = db.get("agents", {})
            return f"🤖 מספר הסוכנים במערכת: {len(agents)}"

        except Exception as e:
            return f"⚠️ לא ניתן לקרוא את מספר הסוכנים: {e}"

    # User count
    if "כמה משתמשים" in q or "מספר המשתמשים" in q:
        try:
            with open("state/db.json", encoding="utf-8") as f:
                db = json.load(f)

            users = db.get("users", {})
            return f"👥 מספר המשתמשים במערכת: {len(users)}"

        except Exception as e:
            return f"⚠️ לא ניתן לקרוא את מספר המשתמשים: {e}"

    # Token information
    if "מה זה slh token" in q or "מה זה token" in q:
        return (
            "🪙 SLH Token הוא רכיב הכלכלה הדיגיטלית של SLH OS. "
            "לבדיקת יתרה או מידע נוסף השתמש בפקודות ה-Token של המערכת."
        )

    # Registration
    if (
        "הרשמה" in q
        or "להירשם" in q
        or "נרשמ" in q
        or "join" in q
    ):
        return "📝 להרשמה למערכת השתמש בפקודה /join"

    return None


def register_ask_handler(bot):

    @bot.message_handler(commands=["ask"])
    def ask(msg):

        question = (msg.text or "").replace("/ask", "", 1).strip()

        if not question:
            bot.reply_to(msg, "Usage: /ask <שאלה>")
            return

        # Duplicate request protection
        if not guard(question):
            bot.reply_to(msg, guarded_message())
            return

        user_id = str(msg.from_user.id)

        # First: local answer, no LLM
        try:
            answer = local_answer(question, user_id)
        except Exception as e:
            answer = f"⚠️ שגיאה בתשובה מקומית: {e}"

        if answer is not None:
            bot.reply_to(msg, answer)
            return

        # Never attempt LLM if provider is unavailable
        if not provider_available("groq"):
            bot.reply_to(
                msg,
                "⏳ שירות ה-AI אינו זמין כרגע. "
                "המערכת לא שלחה את הבקשה לספק חיצוני."
            )
            return

        # LLM fallback
        try:
            answer = query_llm_with_context(question, user_id)
            bot.reply_to(msg, answer)

        except Exception as e:
            bot.reply_to(
                msg,
                f"⚠️ שירות ה-AI לא זמין כרגע.\n"
                f"המערכת נשארה פעילה ולא קרסה."
            )

