def guard(text):
    lower = text.lower()
    if any(x in lower for x in ['api','key','secret','token','password','rm -rf','sudo']):
        return True, '⛔️ בקשתך מכילה מידע רגיש או פקודה מסוכנת – לא ניתן לשלוח ל-LLM.'
    if 'https://' in lower or 'http://' in lower:
        return True, '🔗 זיהיתי קישור – אין ברשותי גישה לתוכן חיצוני.'
    return False, None
