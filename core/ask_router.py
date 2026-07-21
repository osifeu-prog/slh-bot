from core.ask_guard import guard
from core.context_builder import get_context
from core.ask_debug import debug_ask


# ===== ASK Router v1 – Intent Detection =====
INTENTS = {
    "onboarding": ["הרשמה", "להצטרף", "רישום", "איך מתחילים", "איך משתמשים", "מה עושים", "/join"],
    "greeting": ["היי", "שלום", "בוקר טוב", "ערב טוב", "אהלן"],
    "courses": ["קורס", "לימוד", "ביטקוין", "מאסטרי", "אקדמיה", "/courses"],
    "agents": ["סוכן", "סוכנים", "agent", "צור סוכן", "/agents"],
    "help": ["עזרה", "פקודות", "מה אפשר לעשות", "/help"],
    "system": ["הסבר", "מה זה", "מהי המערכת", "איך זה עובד", "להסביר"],
    "general": []
}

def detect_intent(text):
    text_lower = text.strip().lower()
    for intent, keywords in INTENTS.items():
        if intent == "general":
            continue
        for kw in keywords:
            if kw in text_lower:
                return intent
    return "general"





def route(text):
    # Intent Detection (v1)
    intent = detect_intent(text)
    if intent == "onboarding":
        return "📝 בעיית הרשמה?\nהשתמש בפקודה /join"
    elif intent == "greeting":
        return "👋 שלום! איך אוכל לעזור?"
    elif intent == "courses":
        return "🎓 קורסים זמינים:\n/course_bitcoin_mastery"
    elif intent == "agents":
        return "🤖 נסה /agents לרשימת הסוכנים."
    elif intent == "help":
        return "📘 פקודות עיקריות: /start, /join, /courses, /agents, /ask"
    elif intent == "system":
        return "SLH OS היא מערכת AI אוטונומית עם סוכנים, קורסים וכלכלה פנימית."

    # fallback – continue to guard and LLM
    blocked, msg = guard(text)
    if blocked:
        return msg

    debug = debug_ask(text)

    if debug['intent'] == 'agent_count':
        ctx = get_context()
        return f"🤖 מספר סוכנים רשומים: {ctx['agents']}"

    if debug['intent'] == 'user_count':
        ctx = get_context()
        return f"👥 משתמשים במערכת: {ctx['users']}"

    if debug['intent'] == 'token_info':
        return (
            "🪙 SLH Token הוא נכס דיגיטלי במערכת SLH.\n"
            "הוא משמש ככלכלת המערכת, הרשאות, תגמולים ואינטראקציות בתוך האקוסיסטם."
        )

    if debug['intent'] == 'registration_help':
        return (
            "📝 בעיית הרשמה?\n"
            "השתמש בפקודה /join "
            "ואני אוביל אותך שלב אחרי שלב."
        )

    return ""  # LLM fallback – will be handled by advanced_ask_handler
