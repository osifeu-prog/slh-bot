def debug_ask(text):
    lower = text.lower()

    if 'כמה סוכנים' in text:
        return {"intent": "agent_count", "need_llm": False}

    if 'כמה משתמשים' in text:
        return {"intent": "user_count", "need_llm": False}

    if 'מה זה slh token' in lower or 'מה זה token' in lower:
        return {"intent": "token_info", "need_llm": False}

    if (
        'הרשמה' in text
        or 'להירשם' in text
        or 'join' in lower
        or 'נרשמ' in text
    ):
        return {"intent": "registration_help", "need_llm": False}

    return {"intent": "unknown", "need_llm": True}
