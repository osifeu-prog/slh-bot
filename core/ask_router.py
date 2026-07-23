from core.ask_guard import guard
from core.context_builder import get_context
from core.ask_debug import debug_ask


# ===== ASK Router v1 – Intent Detection =====
INTENTS = {
    "onboarding": ["הרשמה", "להצטרף", "רישום", "איך מתחילים", "איך משתמשים", "מה עושים", "/join"],
    "greeting": ["היי", "שלום", "בוקר טוב", "ערב טוב", "אהלן"],
    "courses": ["קורס", "לימוד", "ביטקוין", "מאסטרי", "אקדמיה", "/courses"],
    "analysis": ["נתח", "ניתוח", "תנתח", "מצב המערכת", "שיפור", "איך לשפר", "המלצה", "ארכיטקטורה", "אסטרטגיה"],
    "agents": ["סוכן", "סוכנים", "agent", "צור סוכן", "/agents"],
    "help": ["עזרה", "פקודות", "מה אפשר לעשות", "/help"],
    "system": [
        "הסבר",
        "מה זה",
        "מהי המערכת",
        "איך זה עובד",
        "להסביר",
        "מצב המערכת",
        "סטטוס מערכת",
        "health",
        "status",
        "מצב slh"
    ],
    "general": []
}

PRIORITY = ["system", "agents", "courses", "help", "onboarding", "greeting", "analysis"]

def detect_intent(text):
    text_lower = text.strip().lower()
    for intent in PRIORITY:
        if intent == "general":
            continue
        for kw in INTENTS[intent]:
            if kw in text_lower:
                return intent
    return "general"

def route(text):
    intent = detect_intent(text)
    if intent == "onboarding":
        return "📝 בעיית הרשמה?\nהשתמש בפקודה /join"
    elif intent == "greeting":
        return "👋 שלום! איך אוכל לעזור?"
    elif intent == "courses":
        return "🎓 קורסים זמינים:\n/course_bitcoin_mastery"
    elif intent == "analysis":
        return None  # fallback to LLM
    elif intent == "agents":
        ctx = get_context()
        return f"🤖 מספר הסוכנים הרשומים במערכת: {ctx['agents']}"
    elif intent == "help":
        return "📘 פקודות עיקריות: /start, /join, /courses, /agents, /ask"
    elif intent == "system":
        return "SLH OS היא מערכת AI אוטונומית עם סוכנים, קורסים וכלכלה פנימית."

    result = guard(text); blocked, msg = (result, None) if isinstance(result, bool) else result
    if blocked:
        return msg

    debug = debug_ask(text)
    if debug['intent'] == 'agent_count':
        ctx = get_context()
        return f"🤖 מספר סוכנים רשומים: {ctx['agents']}"

    return None  # fallback to LLM
