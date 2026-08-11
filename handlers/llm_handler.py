from openai import OpenAI
import os
import json
import requests

client = None


def ask_gemini(prompt):
    key = os.getenv("GEMINI_API_KEY")

    if not key:
        return "GEMINI_API_KEY missing"

    url = (
        "https://generativelanguage.googleapis.com/"
        "v1/models/gemini-2.0-flash:generateContent?key=" + key
    )

    data = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }

    try:
        r = requests.post(url, json=data, timeout=20)
        j = r.json()

        if "candidates" in j:
            return j["candidates"][0]["content"]["parts"][0]["text"]

        return "Gemini Error: " + str(j)

    except Exception as e:
        return f"Gemini Error: {e}"


def ask_groq(prompt):
    global client

    try:
        if client is None:
            key = os.getenv("GROQ_API_KEY")

            if not key:
                return "GROQ_API_KEY missing"

            client = OpenAI(
                api_key=key,
                base_url="https://api.groq.com/openai/v1"
            )

        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=500
        )

        return resp.choices[0].message.content

    except Exception as e:

        if "429" in str(e):
            return "LLM Error: Groq rate limit/quota exceeded."

        return f"LLM Error: {e}"


def register_llm_handler(bot):
    print("LLM core loaded (ask handled by advanced_ask_handler)")


def query_llm_with_context(question, uid=None):

    q = str(question).lower()

    try:

        with open("state/db.json", encoding="utf-8") as f:
            db = json.load(f)

        user = db.get("users", {}).get(str(uid), {})
        agents = db.get("agents", {})
        tasks = dict(list(db.get("tasks", {}).items())[-5:])
        votes_raw = db.get("votes", {})
        votes = list(votes_raw.items())[-10:] if isinstance(votes_raw, dict) else votes_raw[-10:]


        # SYSTEM IDENTITY

        if any(x in q for x in [
            "מי אתה",
            "what are you",
            "who are you",
            "מה אתה"
        ]):
            return "אני SLH OS AI assistant. אני המערכת החכמה של SLH OS."


        # OWNER IDENTITY

        if any(x in q for x in [
            "מי אני",
            "who am i",
            "my identity",
            "identity"
        ]):

            if user.get("role") == "OWNER":
                return (
                    f"אתה {user.get('name')} — "
                    "OWNER של SLH OS."
                )

            return f"אתה {user.get('name','unknown')}."


        # NAME

        if any(x in q for x in [
            "name",
            "my name",
            "מה השם שלי",
            "איך קוראים לי"
        ]):

            return f"השם שלך הוא: {user.get('name','unknown')}"


        # ROLE

        if any(x in q for x in [
            "role",
            "permission",
            "תפקיד",
            "הרשאה",
            "מה התפקיד שלי"
        ]):

            return f"התפקיד שלך הוא: {user.get('role','unknown')}"


        # WALLET

        if any(x in q for x in [
            "credit",
            "credits",
            "wallet",
            "balance",
            "קרדיט",
            "יתרה"
        ]):

            return (
                "הקרדיטים שלך: "
                + str(
                    user.get("wallet", {})
                    .get("credits", 0)
                )
            )


        # AGENTS

        if any(x in q for x in [
            "agent",
            "agents",
            "סוכן",
            "סוכנים"
        ]):

            names = [
                a.get("name","?")
                for a in agents.values()
            ]

            return (
                f"סוכנים פעילים: {len(agents)}\n"
                + ", ".join(names)
            )


        context = f"""
SLH SYSTEM STATE:

User:
name={user.get('name')}
role={user.get('role')}
credits={user.get('wallet',{}).get('credits',0)}

Agents:
count={len(agents)}
names={", ".join(
    [a.get("name","?") for a in agents.values()]
)}

Tasks:
{tasks}

Votes:
{votes}
"""


    except Exception as e:

        context = f"Context error: {e}"


    prompt = f"""
You are SLH OS AI assistant.

Answer in Hebrew.
Be concise.

SYSTEM RULES:

- System context is truth.
- Never invent user identity.
- Never invent balances.
- Never invent roles.
- Never call the user a partner/friend/human.

SYSTEM CONTEXT:

{context}


USER QUESTION:

{question}
"""


    return ask_groq(prompt)



def register(bot):
    return register_llm_handler(bot)


print("LLM MODULE LOADED FROM:", __file__)
