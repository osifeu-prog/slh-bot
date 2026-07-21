from core.ask_guard import guard
from core.context_builder import get_context
from core.ask_debug import debug_ask

def route(text):
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
    if debug['intent'] == 'registration':
        return "📝 להרשמה השתמש ב־/join"
    if debug['intent'] == 'token_info':
        return (
            "🪙 SLH Token הוא נכס דיגיטלי במערכת SLH.\n"
            "הוא משמש ככלכלת המערכת, הרשאות, תגמולים ואינטראקציות בתוך האקוסיסטם."
        )

    return None  # LLM
