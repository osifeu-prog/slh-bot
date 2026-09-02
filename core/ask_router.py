import re

from core.ask_guard import guard
from core.context_builder import get_context
from core.ask_debug import debug_ask
from core.economy_service import get_balance_safe
from handlers.llm_handler import query_llm_with_context


def _kw_match(kw, text_lower):
    kwl = kw.lower()
    if not kwl:
        return False
    if re.match(r'^\w', kwl):
        return bool(re.search(r'\b' + re.escape(kwl) + r'\b', text_lower))
    return kwl in text_lower

INTENTS = {
    "missions": ["המשימות שלי","רשימת משימות","my tasks","show tasks","/task"],
    "progress": ["התקדמות","מצב התקדמות","progress"],
    "rewards": ["פרסים","תגמולים","rewards"],
    "wallet": ["קרדיטים","קרדיט","credits","credit","balance","יתרה","היתרה שלי","כמה יש לי","ארנק","wallet"],
    "staking": ["סטייקינג","stake","staked","נעל","נעלתי","כמה סטייק"],
    "onboarding": ["הרשמה","להצטרף","רישום","איך מתחילים","איך משתמשים","מה עושים","/join"],
    "greeting": ["היי","שלום","בוקר טוב","ערב טוב","אהלן"],
    "courses": ["/courses","הקורס שלי","רשימת קורסים","אקדמיה"],
    "analysis": ["נתח","ניתוח","תנתח","שיפור","איך לשפר","המלצה","ארכיטקטורה","אסטרטגיה"],
    "agents": ["סוכן","סוכנים","agent","צור סוכן","/agents","כמה סוכנים"],
    "help": ["עזרה","מה אפשר לעשות","/help","עזרה בבקשה"],
    "system": ["מהי המערכת","מצב המערכת","סטטוס המערכת","health","status"],
    "general": []
}

FORBIDDEN_ASK_TOPICS = ["launch_state","launch","alpha_open","alpha","blocked","ready","p0","משימות p0","כמה משימות","האם סגרנו","מה המצב","סטטוס מערכת","מצב המערכת","האם המערכת","כמה משתמשים","יתרות","staked","credits","ארנק של","כמה כסף","אבטחה","הרשאות","gate","חסימה"]

def is_system_state_question(text):
    text_lower = text.strip().lower()
    return any(_kw_match(t, text_lower) for t in FORBIDDEN_ASK_TOPICS)

PRIORITY = ["staking","wallet","progress","rewards","system","agents","courses","help","onboarding","greeting","analysis","missions"]

def detect_intent(text):
    text_lower = text.strip().lower()

    # Greeting is valid only when the entire message is a greeting.
    # This prevents questions containing a greeting from being swallowed.
    greeting_exact = {
        kw.strip().lower()
        for kw in INTENTS.get("greeting", [])
        if kw.strip()
    }

    if text_lower in greeting_exact:
        return "greeting"

    question_words = ["כיצד", "איך", "מה", "מדוע", "למה", "הסבר", "explain", "how", "what", "why"]
    if any(word in text_lower for word in question_words):
        return "general"

    for intent in PRIORITY:
        if intent == "greeting":
            continue

        for kw in INTENTS[intent]:
            if kw and _kw_match(kw, text_lower):
                return intent

    return "general"

def route(text, uid=None):
    guard_result = guard(text)
    if isinstance(guard_result, tuple):
        blocked, msg = guard_result
    else:
        allowed = bool(guard_result)
        blocked = not allowed
        msg = "הבקשה כבר בטיפול. נסה שוב בעוד כמה שניות."
    if blocked:
        return msg

    intent = detect_intent(text)

    # Educational / how-to questions should hit LLM, not rigid menus
    _explain = ("כיצד", "איך ", "how ", "explain", "what is", "מהו ", "מה היתרון", "תאר", "describe", "write a", "כתוב ")
    tl = text.strip().lower()
    if any(x in tl for x in _explain) and intent in ("missions", "help", "agents", "system", "rewards"):
        intent = "general"


    if intent == "staking":
        base = "סטייקינג SLH\n\n1. קנה credits עם Stars: /pay\n2. נעל אותם: /stake <amount>\n\nסטייקינג פנימי בלבד, לא on-chain."
        if uid:
            try:
                from core import economy_service
                staked = economy_service.get_staked_safe(uid)
                return f"{base}\n\nהסטייקינג שלך: {staked} credits"
            except Exception:
                pass
        return base

    if intent == "wallet":
        if uid is None:
            return "לא ניתן לזהות את המשתמש."
        try:
            credits = get_balance_safe(str(uid))
            return f"היתרה שלך: {credits} credits"
        except Exception as e:
            if str(e) == "USER_NOT_FOUND":
                return "המשתמש לא נמצא במערכת."
            return "לא ניתן לקרוא כרגע את יתרת הארנק."

    elif intent == "missions":
        try:
            from core.mission_lifecycle import MissionLifecycleService
            service = MissionLifecycleService()
            board, _ = service.load_state()
            missions = board.get("missions") or board.get("tasks") or []
            return "משימות:\n" + str(missions)
        except Exception:
            return "אין משימות פעילות כרגע."

    elif intent == "progress":
        try:
            from core.profile_manager import get_progress
            return "התקדמות:\n" + str(get_progress(uid))
        except Exception:
            return "לא ניתן לקרוא התקדמות כרגע."

    elif intent == "rewards":
        try:
            from core.reward_engine import _load
            rewards = [r for r in _load() if str(r.get("user")) == str(uid)]
            return "תגמולים:\n" + str(rewards)
        except Exception:
            return "אין תגמולים זמינים כרגע."

    elif intent == "onboarding":
        return "בעיית הרשמה?\nהשתמש בפקודה /join"

    elif intent == "greeting":
        return "שלום! איך אוכל לעזור?"

    elif intent == "courses":
        return "קורסים זמינים:\n/course_bitcoin_mastery"

    elif intent == "analysis":
        pass

    elif intent == "agents":
        return "נסה /agents לרשימת הסוכנים."

    elif intent == "help":
        return "פקודות עיקריות: /start, /join, /courses, /agents, /ask"

    elif intent == "system":
        return "SLH OS היא מערכת AI אוטונומית עם סוכנים, קורסים וכלכלה פנימית."

    debug = debug_ask(text)
    if debug["intent"] == "agent_count":
        ctx = get_context()
        return f"מספר סוכנים רשומים: {ctx['agents']}"

    if is_system_state_question(text):
        return "ask אינו מוסמך לענות על שאלות מצב מערכת. השתמש בפקודות בדיקה: e או exec (לקריאה) או בדיקות ידניות."
    try:
        return query_llm_with_context(text, uid=str(uid) if uid is not None else None)
    except Exception:
        return "מנוע ה-AI לא זמין כרגע, נסה שוב מאוחר יותר."