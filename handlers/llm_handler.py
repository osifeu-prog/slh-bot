import json, os
from groq import Groq

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

def get_bot_context(uid: str) -> str:
    try:
        with open("state/db.json") as f:
            db = json.load(f)
    except:
        db = {}
    user = db.get("users", {}).get(uid, {})
    ctx = f"User: {user.get('name','')} (ID: {uid})\n"
    ctx += f"Balance: {user.get('balance',0)} credits\nRole: {user.get('role','user')}\n"
    student = db.get("students", {}).get(uid, {})
    courses = student.get("courses", {})
    if courses:
        ctx += "Courses:\n"
        for cid, cdata in courses.items():
            ctx += f"- {cid}: {cdata.get('progress',0)}%\n"
    tasks = db.get("user_tasks", {}).get(uid, [])
    if tasks:
        ctx += "Tasks:\n" + "\n".join(f"- {t}" for t in tasks[:10]) + "\n"
    agents = db.get("agents", {})
    if agents:
        ctx += "Agents:\n"
        for aid, a in list(agents.items())[:5]:
            ctx += f"- {a.get('name', aid)} [{a.get('state','idle')}]\n"
    journal_path = "state/journal.json"
    if os.path.exists(journal_path):
        try:
            with open(journal_path) as f:
                journal = json.load(f)
            if isinstance(journal, list):
                for e in journal[-3:]:
                    ctx += f"Journal: {e.get('ts','')}: {e.get('text','')}\n"
        except:
            pass
    return ctx

def register(bot):
    @bot.message_handler(commands=['ask'])
    def ask_llm(m):
        uid = str(m.chat.id)
        query = m.text.replace("/ask", "", 1).strip()
        if not query:
            bot.reply_to(m, "Usage: /ask <question>")
            return
        context = get_bot_context(uid)
        system_msg = (
            "You are SLH Assistant, an AI helper for the SLH learning platform. "
            "Use the provided user context to answer questions, give advice, "
            "and suggest actions within the platform.\n\n"
            "Context:\n" + context
        )
        try:
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": query}
                ],
                temperature=0.7,
                max_tokens=500
            )
            answer = resp.choices[0].message.content
        except Exception as e:
            answer = f"⚠️ LLM error: {e}"
        bot.reply_to(m, answer)
