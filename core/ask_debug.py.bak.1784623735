def debug_ask(text):
    result = {
        "input": text,
        "lang": "he" if any(c in text for c in 'אבגדהוזחטיכלמנסעפצקרשתךםןףץ') else "unknown",
        "intent": "unknown",
        "confidence": 0,
        "need_llm": True,
        "warnings": []
    }
    lower = text.lower()
    if any(kw in lower for kw in ['api','key','secret','token','password','rm -rf']):
        result['warnings'].append('sensitive_keyword')
        result['need_llm'] = False
    if 'כמה סוכנים' in text or 'agent count' in lower:
        result['intent'] = 'agent_count'
        result['confidence'] = 0.9
        result['need_llm'] = False
    if 'כמה משתמשים' in text or 'user count' in lower:
        result['intent'] = 'user_count'
        result['confidence'] = 0.9
        result['need_llm'] = False
    if 'הרשמ' in text or 'join' in lower:
        result['intent'] = 'registration'
        result['confidence'] = 0.8
        result['need_llm'] = False
    return result
