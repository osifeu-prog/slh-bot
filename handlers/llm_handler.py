import json, os
from groq import Groq

def query_llm_with_context(question, user_id):
    k = os.getenv("GROQ_API_KEY")
    if not k:
        return "שגיאה: GROQ_API_KEY חסר"

    try:
        with open("state/db.json", encoding="utf-8") as f:
            db = json.load(f)
    except:
        db = {}
    try:
        with open("state/agents.json", encoding="utf-8") as f:
            agents = json.load(f)
    except:
        agents = {}

    users_count = len(db.get("users", {}))
    agents_count = len(agents)
    user = db.get("users", {}).get(str(user_id), {})

    context = (
        f"משתמשים רשומים: {users_count}\n"
        f"סוכני AI: {agents_count}\n"
        f"שם משתמש: {user.get('name', 'לא ידוע')}\n"
        f"יתרה: {user.get('balance', 0)} SLH\n"
        f"קורס פעיל: {user.get('active_course', 'אין')}"
    )

    try:
        client = Groq(api_key=k)
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "אתה רובוטוש – העוזר האישי של SLH OS. ענה בעברית תמציתי וברור. השתמש אך ורק בנתוני המערכת."},
                {"role": "user", "content": context + "\n\nשאלה: " + question}
            ],
            max_tokens=200
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"שגיאה: {e}"
