def guard(text):
    lower = text.lower()
    dangerous = ['rm -rf', 'sudo ', 'drop table', 'delete from', 'shutdown', 'reboot']
    for pattern in dangerous:
        if pattern in lower:
            return True, '⛔️ בקשתך מכילה פקודה מסוכנת – לא ניתן לשלוח ל-LLM.'
    if 'https://' in lower or 'http://' in lower:
        return True, '🔗 זיהיתי קישור – אין ברשותי גישה לתוכן חיצוני.'
    return False, None
