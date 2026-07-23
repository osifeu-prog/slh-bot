from pathlib import Path

p = Path("core/ask_router.py")
s = p.read_text(encoding="utf-8")

s = s.replace(
'''    "analysis": ["נתח", "ניתוח", "תנתח", "מצב המערכת", "שיפור", "איך לשפר", "המלצה",
"ארכיטקטורה", "אסטרטגיה"],''',
'''    "analysis": ["נתח", "ניתוח", "תנתח", "שיפור", "איך לשפר", "המלצה",
"ארכיטקטורה", "אסטרטגיה"],'''
)

s = s.replace(
'''    "system": ["הסבר", "מה זה", "מהי המערכת", "איך זה עובד", "להסביר"],''',
'''    "system": [
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
    ],'''
)

s = s.replace(
'''PRIORITY = ["analysis", "system", "agents", "courses", "help", "onboarding", "greeting"]''',
'''PRIORITY = ["system", "agents", "courses", "help", "onboarding", "greeting", "analysis"]'''
)

s = s.replace(
'''    elif intent == "agents":
        return "🤖 נסה /agents לרשימת הסוכנים."''',
'''    elif intent == "agents":
        ctx = get_context()
        return f"🤖 מספר הסוכנים הרשומים במערכת: {ctx['agents']}"'''
)

p.write_text(s, encoding="utf-8")

print("SLH ASK ROUTER PATCH COMPLETE")
