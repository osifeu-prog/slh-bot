import re
from datetime import datetime
from zoneinfo import ZoneInfo

from core.ask_guard import guard
from core.context_builder import get_context
from core.ask_debug import debug_ask
from core.economy_service import get_balance_safe
from handlers.llm_handler import query_llm_with_context

MINI_APP_URL = "https://web-production-22f28.up.railway.app/mini-app?v=20260918-system"


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
    "dashboard": ["dashboard","לוח המחוונים","דשבורד"],
    "analysis": ["נתח","ניתוח","תנתח","שיפור","איך לשפר","המלצה","ארכיטקטורה","אסטרטגיה"],
    "agents": ["סוכן","סוכנים","agent","צור סוכן","/agents","כמה סוכנים"],
    "help": ["עזרה","מה אפשר לעשות","/help","עזרה בבקשה"],
    "system": ["מהי המערכת","מצב המערכת","סטטוס המערכת","health","status"],
    "time": ["מה השעה","מה הזמן","השעה","what time is it","what time"],
    "general": []
}

FORBIDDEN_ASK_TOPICS = ["p0", "משימות p0", "חסימה"] # "p0", "משימות p0", "חסימה"] # "launch_state","launch","alpha_open","alpha","blocked","ready","p0","משימות p0","כמה משימות","האם סגרנו","מה המצב","סטטוס מערכת","מצב המערכת","האם המערכת","כמה משתמשים","יתרות","staked","credits","ארנק של","כמה כסף","אבטחה","הרשאות","gate","חסימה"]


def is_system_state_question(text):
    text_lower = text.strip().lower()
    return any(_kw_match(t, text_lower) for t in FORBIDDEN_ASK_TOPICS)


PRIORITY = ["time","staking","wallet","progress","rewards","system","agents","courses","dashboard","help","onboarding","greeting","analysis","missions"]


def detect_intent(text):
    text_lower = text.strip().lower()
    greeting_exact = {kw.strip().lower() for kw in INTENTS.get("greeting", []) if kw.strip()}
    if text_lower in greeting_exact:
        return "greeting"

    if len(text_lower) <= 40:
        for kw in INTENTS["time"]:
            if kw and _kw_match(kw, text_lower):
                return "time"

    if len(text_lower) <= 40 and any(x in text_lower for x in ("קורס", "שיעור", "academy", "אקדמיה")) and any(x in text_lower for x in ("איך", "כיצד", "להשלים", "להתחיל", "where", "how")):
        return "courses"
    if any(x in text_lower for x in ("dashboard", "לוח המחוונים", "דשבורד")):
        return "dashboard"

    if len(text_lower) <= 40:
        for intent in ("staking", "wallet"):
            for kw in INTENTS[intent]:
                if kw and _kw_match(kw, text_lower):
                    return intent

    question_words = ["כיצד", "איך", "מה", "מדוע", "למה", "הסבר", "explain", "how", "what", "why"]
    if any(word in text_lower for word in question_words):
        return "general"

    for intent in PRIORITY:
        if intent in ("staking", "wallet", "greeting", "time"):
            continue
        for kw in INTENTS[intent]:
            if kw and _kw_match(kw, text_lower):
                return intent
    return "general"


def route(text, uid=None):
    if re.search(r"\[\d{1,2}/\d{1,2}/\d{4}", str(text or "")):
        return "נראה שהודבק לוג שיחה. אני לא עונה על לוגים, כדי לא לענות בשם אחרים. שלח שאלה קצרה או פקודה."
    guard_result = guard(text, uid)
    if isinstance(guard_result, tuple):
        blocked, msg = guard_result
    else:
        allowed = bool(guard_result)
        blocked = not allowed
        msg = "הבקשה כבר בטיפול. נסה שוב בעוד כמה שניות."
    if blocked:
        return msg

    intent = detect_intent(text)

    # Build canonical project context for every AI session without exposing secrets.
    try:
        from core.project_context import get_project_context
        project_context = get_project_context(uid, "slh-canonical")
    except Exception:
        project_context = None
    _explain = ("כיצד", "איך ", "how ", "explain", "what is", "מהו ", "מה היתרון", "תאר", "describe", "write a", "כתוב ")
    tl = text.strip().lower()
    if any(x in tl for x in _explain) and intent in ("missions", "help", "agents", "system", "rewards"):
        intent = "general"

    if intent == "time":
        now = datetime.now(ZoneInfo("Asia/Jerusalem"))
        return f"השעה הנוכחית בישראל היא {now:%H:%M}"

    if intent == "staking":
        base = ("סטייקינג SLH\n\n" "אין צורך להשלים קורס כדי לבצע Staking. זה מנגנון פנימי של Credits.\n" "אין צורך לחפש Dashboard נפרד.\n\n" "הפעלת Staking: /stake <amount>\n" "צפייה בסטייקינג: /my_stake\n\n" "Academy הוא מסלול לימודי נפרד ואינו תנאי ל-Staking.\n\n" "סטייקינג פנימי בלבד, לא on-chain.")
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

    if intent == "missions":
        try:
            from core.mission_lifecycle import MissionLifecycleService
            service = MissionLifecycleService()
            board, _ = service.load_state()
            missions = board.get("missions") or board.get("tasks") or []
            if isinstance(missions, dict):
                missions = list(missions.values())
            lines = []
            for m in missions:
                if not isinstance(m, dict):
                    lines.append(str(m)); continue
                status = m.get("status", "?")
                desc = m.get("desc", m.get("description", "?"))
                agent = m.get("assigned_to") or "לא שויך"
                lines.append(f"#{m.get('id', '?')} [{status}] {desc} (אחראי: {agent})")
            return "משימות:\n" + "\n".join(lines) if lines else "אין משימות פעילות כרגע."
        except Exception:
            return "אין משימות פעילות כרגע."

    if intent == "progress":
        try:
            from core.progress_tracker import progress_report
            return progress_report()
        except Exception:
            return "לא ניתן לקרוא התקדמות כרגע."

    if intent == "rewards":
        try:
            from core.reward_engine import _load
            rewards = [r for r in _load() if str(r.get("user")) == str(uid)]
            if not rewards:
                return "אין תגמולים זמינים כרגע."
            lines = []
            for r in rewards:
                if isinstance(r, dict):
                    lines.append(f"• {r.get('reason', 'תגמול')}: {r.get('credits', 0)} credits, {r.get('points', 0)} points")
                else:
                    lines.append(str(r))
            return "תגמולים:\n" + "\n".join(lines)
        except Exception:
            return "אין תגמולים זמינים כרגע."

    if intent == "onboarding":
        return "בעיית הרשמה?\nהשתמש בפקודה /join"
    if intent == "greeting":
        return "שלום! איך אוכל לעזור?"
    if intent == "courses":
        return ("🎓 Academy – Bitcoin Mastery\n\n" "ה-Academy הוא מסלול לימודי נפרד. אין צורך להשלים קורס כדי לבצע Staking.\n\n" "1. /course_bitcoin_mastery\n" "2. /lesson bitcoin_mastery 1\n" "3. כשסיימת: /finish bitcoin_mastery 1\n" "4. חזור על 2–3 עבור שיעורים 2 ו-3.\n" "5. /academy_progress\n\n" "Staking זמין בנפרד דרך /stake <amount>.")
    if intent == "dashboard":
        return f"📊 אין Dashboard נפרד למשתמשים. הממשק הקיים הוא SLH Market Mini App:\n{MINI_APP_URL}"
    if intent == "agents":
        return "נסה /agents לרשימת הסוכנים."
    if intent == "help":
        return "פקודות עיקריות: /start, /join, /courses, /agents, /ask"
    if intent == "system":
        return "SLH OS היא מערכת AI אוטונומית עם סוכנים, קורסים וכלכלה פנימית."

    debug = debug_ask(text)
    if debug["intent"] == "agent_count":
        ctx = get_context()
        return f"מספר סוכנים רשומים: {ctx['agents']}"

    if is_system_state_question(text):
        return "ask אינו מוסמך לענות על שאלות מצב מערכת. השתמש בפקודות בדיקה: e או exec (לקריאה) או בדיקות ידניות."
    try:
        enriched = text
        if project_context:
            enriched += "\n\n[PROJECT_CONTEXT]\n" + str({
                "project_id": project_context.get("project_id"),
                "agents": project_context.get("agents", {}).get("count", 0),
                "services": len(project_context.get("services", [])),
                "runtime": project_context.get("runtime", {}).get("running", False),
            })
        return query_llm_with_context(enriched, uid=str(uid) if uid is not None else None)
    except Exception:
        return "מנוע ה-AI לא זמין כרגע, נסה שוב מאוחר יותר."
