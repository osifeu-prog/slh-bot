from core.ask_guard import guard
from core.context_builder import get_context
from core.ask_debug import debug_ask
from core.economy_service import get_balance_safe


# ===== ASK Router v2 – Deterministic + LLM fallback =====

INTENTS = {
    "missions": ["משימות","המשימות","tasks","missions"],
    "progress": ["התקדמות","מצב התקדמות","progress"],
    "rewards": ["פרסים","תגמולים","rewards"],
    "wallet": [
        "קרדיטים",
        "קרדיט",
        "credits",
        "credit",
        "balance",
        "יתרה",
        "היתרה שלי",
        "כמה יש לי",
        "ארנק",
        "wallet",
        "staked",
        "סטייקינג",
        "סטייק",
        "כמה סטייק",
    ],
    "onboarding": ["הרשמה", "להצטרף", "רישום", "איך מתחילים", "איך משתמשים", "מה עושים", "/join"],
    "greeting": ["היי", "שלום", "בוקר טוב", "ערב טוב", "אהלן"],
    "courses": ["קורס", "לימוד", "ביטקוין", "מאסטרי", "אקדמיה", "/courses"],
    "analysis": ["נתח", "ניתוח", "תנתח", "מצב המערכת", "שיפור", "איך לשפר", "המלצה", "ארכיטקטורה", "אסטרטגיה"],
    "agents": ["סוכן", "סוכנים", "agent", "צור סוכן", "/agents", "כמה סוכנים"],
    "help": ["עזרה", "פקודות", "מה אפשר לעשות", "/help"],
    "system": [
        "הסבר",
        "מה זה",
        "מהי המערכת",
        "איך זה עובד",
        "להסביר",
        "מצב המערכת",
        "סטטוס המערכת",
        "health",
        "status",
    ],
    "general": []
}

PRIORITY = [
    "wallet",
    "missions",
    "progress",
    "rewards",
    "system",
    "agents",
    "courses",
    "help",
    "onboarding",
    "greeting",
    "analysis",
]


def detect_intent(text):
    text_lower = text.strip().lower()

    for intent in PRIORITY:
        for kw in INTENTS[intent]:
            if kw in text_lower:
                return intent

    return "general"


def route(text, uid=None):
    intent = detect_intent(text)

    if intent == "wallet":
        if uid is None:
            return "⚠️ לא ניתן לזהות את המשתמש."

        try:
            credits = get_balance_safe(str(uid))
            return f"💰 היתרה שלך: {credits} credits"
        except Exception as e:
            if str(e) == "USER_NOT_FOUND":
                return "⚠️ המשתמש לא נמצא במערכת."
            return "⚠️ לא ניתן לקרוא כרגע את יתרת הארנק."

    elif intent == "missions":
        try:
            from core.mission_lifecycle import MissionLifecycleService
            service = MissionLifecycleService()
            board, _ = service.load_state()

            missions = (
                board.get("missions")
                or board.get("tasks")
                or []
            )

            return "📋 משימות:\n" + str(missions)
        except Exception:
            return "📋 אין משימות פעילות כרגע."

    elif intent == "progress":
        try:
            from core.profile_manager import get_progress
            return "📈 התקדמות:\n" + str(get_progress(uid))
        except Exception:
            return "📈 לא ניתן לקרוא התקדמות כרגע."

    elif intent == "rewards":
        try:
            from core.reward_engine import _load
            rewards = [
                r for r in _load()
                if str(r.get("user")) == str(uid)
            ]
            return "🏆 תגמולים:\n" + str(rewards)
        except Exception:
            return "🏆 אין תגמולים זמינים כרגע."

    elif intent == "onboarding":
        return "📝 בעיית הרשמה?\nהשתמש בפקודה /join"

    elif intent == "greeting":
        return "👋 שלום! איך אוכל לעזור?"

    elif intent == "courses":
        return "🎓 קורסים זמינים:\n/course_bitcoin_mastery"

    elif intent == "analysis":
        return None

    elif intent == "agents":
        return "🤖 נסה /agents לרשימת הסוכנים."

    elif intent == "help":
        return "📘 פקודות עיקריות: /start, /join, /courses, /agents, /ask"

    elif intent == "system":
        return "SLH OS היא מערכת AI אוטונומית עם סוכנים, קורסים וכלכלה פנימית."

    guard_result = guard(text)

    if isinstance(guard_result, tuple):
        blocked, msg = guard_result
    else:
        allowed = bool(guard_result)
        blocked = not allowed
        msg = "⏳ הבקשה כבר בטיפול. נסה שוב בעוד כמה שניות."

    if blocked:
        return msg

    debug = debug_ask(text)

    if debug["intent"] == "agent_count":
        ctx = get_context()
        return f"🤖 מספר סוכנים רשומים: {ctx['agents']}"

    return None
