from core.ask_guard import guard
from core.context_builder import get_context
from core.ask_debug import debug_ask


# ===== ASK Router v1 ג€“ Intent Detection =====
INTENTS = {
    "onboarding": ["׳”׳¨׳©׳׳”", "׳׳”׳¦׳˜׳¨׳£", "׳¨׳™׳©׳•׳", "׳׳™׳ ׳׳×׳—׳™׳׳™׳", "׳׳™׳ ׳׳©׳×׳׳©׳™׳", "׳׳” ׳¢׳•׳©׳™׳", "/join"],
    "greeting": ["׳”׳™׳™", "׳©׳׳•׳", "׳‘׳•׳§׳¨ ׳˜׳•׳‘", "׳¢׳¨׳‘ ׳˜׳•׳‘", "׳׳”׳׳"],
    "courses": ["׳§׳•׳¨׳¡", "׳׳™׳׳•׳“", "׳‘׳™׳˜׳§׳•׳™׳", "׳׳׳¡׳˜׳¨׳™", "׳׳§׳“׳׳™׳”", "/courses"],
    "analysis": ["׳ ׳×׳—", "׳ ׳™׳×׳•׳—", "׳×׳ ׳×׳—", "׳׳¦׳‘ ׳”׳׳¢׳¨׳›׳×", "׳©׳™׳₪׳•׳¨", "׳׳™׳ ׳׳©׳₪׳¨", "׳”׳׳׳¦׳”", "׳׳¨׳›׳™׳˜׳§׳˜׳•׳¨׳”", "׳׳¡׳˜׳¨׳˜׳’׳™׳”"],
    "agents": ["׳¡׳•׳›׳", "׳¡׳•׳›׳ ׳™׳", "agent", "׳¦׳•׳¨ ׳¡׳•׳›׳", "/agents"],
    "help": ["׳¢׳–׳¨׳”", "׳₪׳§׳•׳“׳•׳×", "׳׳” ׳׳₪׳©׳¨ ׳׳¢׳©׳•׳×", "/help"],
    "system": [
        "׳”׳¡׳‘׳¨",
        "׳׳” ׳–׳”",
        "׳׳”׳™ ׳”׳׳¢׳¨׳›׳×",
        "׳׳™׳ ׳–׳” ׳¢׳•׳‘׳“",
        "׳׳”׳¡׳‘׳™׳¨",
        "׳׳¦׳‘ ׳”׳׳¢׳¨׳›׳×",
        "׳¡׳˜׳˜׳•׳¡ ׳׳¢׳¨׳›׳×",
        "health",
        "status",
        "׳׳¦׳‘ slh"
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
        return "נ“ ׳‘׳¢׳™׳™׳× ׳”׳¨׳©׳׳”?\n׳”׳©׳×׳׳© ׳‘׳₪׳§׳•׳“׳” /join"
    elif intent == "greeting":
        return "נ‘‹ ׳©׳׳•׳! ׳׳™׳ ׳׳•׳›׳ ׳׳¢׳–׳•׳¨?"
    elif intent == "courses":
        return "נ“ ׳§׳•׳¨׳¡׳™׳ ׳–׳׳™׳ ׳™׳:\n/course_bitcoin_mastery"
    elif intent == "analysis":
        return None  # fallback to LLM
    elif intent == "agents":
        ctx = get_context()
        return f"נ₪– ׳׳¡׳₪׳¨ ׳”׳¡׳•׳›׳ ׳™׳ ׳”׳¨׳©׳•׳׳™׳ ׳‘׳׳¢׳¨׳›׳×: {ctx['agents']}"
    elif intent == "help":
        return "נ“˜ ׳₪׳§׳•׳“׳•׳× ׳¢׳™׳§׳¨׳™׳•׳×: /start, /join, /courses, /agents, /ask"
    elif intent == "system":
        return "SLH OS ׳”׳™׳ ׳׳¢׳¨׳›׳× AI ׳׳•׳˜׳•׳ ׳•׳׳™׳× ׳¢׳ ׳¡׳•׳›׳ ׳™׳, ׳§׳•׳¨׳¡׳™׳ ׳•׳›׳׳›׳׳” ׳₪׳ ׳™׳׳™׳×."

    # blocked, msg = guard(text)  # DISABLED
    # if blocked:  # DISABLED
        return msg

    debug = debug_ask(text)
    if debug['intent'] == 'agent_count':
        ctx = get_context()
        return f"נ₪– ׳׳¡׳₪׳¨ ׳¡׳•׳›׳ ׳™׳ ׳¨׳©׳•׳׳™׳: {ctx['agents']}"

    return None  # fallback to LLM
