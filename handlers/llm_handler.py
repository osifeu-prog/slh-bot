import json, os
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
    ctx += f"Registered agents: {total_agents}\n\n"

    ctx += f"User: {user.get('name','')} (ID: {uid})\n"
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
