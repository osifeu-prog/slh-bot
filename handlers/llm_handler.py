import json, os
from datetime import datetime
from groq import Groq

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = None

def get_client():
    global client
    if client is None:
        key = os.getenv("GROQ_API_KEY")
        if not key:
            raise RuntimeError("GROQ_API_KEY missing")
        client = Groq(api_key=key)
    return client

def get_bot_context(uid: str) -> str:
    try:
        with open("state/db.json") as f:
            db = json.load(f)
    except:
        db = {}
    user = db.get("users", {}).get(uid, {})
    
    total_users = len(db.get("users", {}))
    total_agents = len(db.get("agents", {}))

    ctx = f"SLH SYSTEM METRICS:\n"
    ctx += f"משתמשים רשומים במערכת: {total_users}\n"
    ctx += f"סוכני AI במערכת: {total_agents}\n\n"

    ctx += f"User: {user.get('name','')} (ID: {uid})\n"

    # HARD SYSTEM FACTS
    joined = user.get("joined", False)
    onboarding = user.get("onboarding", {})
    credits = user.get("wallet", {}).get("credits", 0)

    ctx += "SYSTEM FACTS (authoritative):\n"
    ctx += f"- User registered: {joined}\n"
    ctx += f"- Onboarding completed: {onboarding.get('completed', False)}\n"
    ctx += f"- Wallet credits: {credits}\n"

    if joined:
        ctx += "- RULE: User is already registered. Never ask for registration again.\n"
        ctx += "- RULE: Continue directly to user interface/help/actions.\n"

    ctx += f"Role: {user.get('role','user')}\n"
    ctx += "\nAUTHORITATIVE SLH OS COMMANDS:\n"
    ctx += "- /balance — בדיקת יתרת Credits של המשתמש\n"
    ctx += "- /pay — רכישת Credits באמצעות תשלום\n"
    ctx += "- /buy — רכישת פריטים או Credits, אם זמין במערכת\n"
    ctx += "- /token balance — בדיקת יתרת SLH Token\n"
    ctx += "- /token supply — בדיקת היצע ה-SLH Token\n"
    ctx += "- /token send <user_id> <amount> — שליחת SLH Token\n"
    ctx += "- /stake — הצגת מצב Staking\n"
    ctx += "- /stake_join — הצטרפות ל-Staking\n"
    ctx += "- /staking_report — דוח Staking ותגמולים\n"
    ctx += "- RULE: When the user asks how to perform an action, prefer the authoritative command above. Do not invent alternative menus, pages, marketplaces, or purchase systems.\n"
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
    journal_path = "journal.json"
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

    @bot.message_handler(commands=['journal_ask'])
    def journal_ask(m):
        question = m.text.replace('/journal_ask', '').strip()
        if not question:
            bot.reply_to(m, "Usage: /journal_ask <question>")
            return
        
        journal_path = "journal.json"
        context = ""
        if os.path.exists(journal_path):
            try:
                with open(journal_path) as f:
                    journal = json.load(f)
                if isinstance(journal, list):
                    context = "Journal:\n" + "\n".join(
                        e.get("text", str(e))[:200] for e in journal[-5:]
                    )
            except:
                context = "(could not read journal)"
        
        try:
            import groq
            client = groq.Client(api_key=os.getenv("GROQ_API_KEY"))
            prompt = f"Based on this journal:\n{context}\n\nQuestion: {question}\n\nAnswer in Hebrew, concise:"
            response = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.1-8b-instant",
                max_tokens=300
            )
            answer = response.choices[0].message.content
        except Exception as e:
            answer = f"(LLM unavailable: {e})"
        
        try:
            with open(journal_path) as f:
                journal = json.load(f)
            journal.append({"time": str(datetime.now()), "type": "llm_ask", "question": question, "answer": answer})
            with open(journal_path, "w") as f:
                json.dump(journal, f, indent=2, ensure_ascii=False)
        except:
            pass
        
        bot.reply_to(m, f"🧠 {answer}")

    # Legacy stub.
    # /ask is now handled exclusively by advanced_ask_handler.py
    pass


def is_llm_available():
    """
    Health check for SLH doctor.
    Does not call the API.
    """
    import os
    return bool(os.getenv("GROQ_API_KEY"))


def query_llm(question):
    """
    Main LLM gateway for ASK.
    """
    client = get_client()

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "system",
                "content": "You are SLH OS AI assistant. Answer in Hebrew when possible."
            },
            {
                "role": "user",
                "content": question
            }
        ],
        max_tokens=500
    )

    return response.choices[0].message.content
