from openai import OpenAI
import os

client = None

def ask_gemini(prompt):
    import requests, os
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return "GEMINI_API_KEY missing"

    url = "https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent?key=" + key
    data = {"contents":[{"parts":[{"text":prompt}]}]}

    r = requests.post(url, json=data, timeout=20)
    j = r.json()

    return j["candidates"][0]["content"]["parts"][0]["text"] if "candidates" in j else "Gemini Error: " + str(j)


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
    """
    Disabled command registration.
    /ask ownership moved to advanced_ask_handler.
    """
    print("LLM core loaded (ask handled by advanced_ask_handler)")



def query_llm_with_context(question, uid=None):
    import json

    q = str(question).lower()

    try:
        with open("state/db.json", encoding="utf-8") as f:
            db = json.load(f)

        user = db.get("users", {}).get(str(uid), {})
        agents = db.get("agents", {})

        # HARD FACT: user name
        name_terms = [
            "name",
            "my name",
            "what is my name",
            "\u05de\u05d4 \u05d4\u05e9\u05dd \u05e9\u05dc\u05d9",
            "\u05d0\u05d9\u05da \u05e7\u05d5\u05e8\u05d0\u05d9\u05dd \u05dc\u05d9",
            "\u05e9\u05dd"
        ]

        if any(x in q for x in name_terms):
            return f"Your name is: {user.get('name', 'unknown')}"


        # HARD FACT: user role / identity
        role_terms = [
            "role",
            "permission",
            "identity",
            "who am i",
            "what is my role",
            "\u05ea\u05e4\u05e7\u05d9\u05d3",
            "\u05de\u05d9 \u05d0\u05e0\u05d9",
            "\u05d4\u05e8\u05e9\u05d0\u05d4",
            "\u05de\u05d4 \u05d4\u05ea\u05e4\u05e7\u05d9\u05d3 \u05e9\u05dc\u05d9"
        ]

        if any(x in q for x in role_terms):
            return f"Your role is: {user.get('role', 'unknown')}"

        # HARD FACT: user credits / wallet
        credit_terms = [
            "credit",
            "credits",
            "balance",
            "wallet",
            "\u05e7\u05e8\u05d3\u05d9\u05d8",
            "\u05e7\u05e8\u05d3\u05d9\u05d8\u05d9\u05dd",
            "\u05d9\u05ea\u05e8\u05d4",
            "\u05db\u05de\u05d4 \u05d9\u05e9 \u05dc\u05d9",
            "\u05db\u05de\u05d4 \u05e7\u05e8\u05d3\u05d9\u05d8\u05d9\u05dd \u05d9\u05e9 \u05dc\u05d9"
        ]

        if any(x in q for x in credit_terms):
            return f"Your credits are: {user.get('wallet', {}).get('credits', 0)}"

        # ABSOLUTE AGENT LOCK: never send agent facts to LLM
        agent_terms = [
            "agent",
            "agents",
            "\u05e1\u05d5\u05db\u05df",
            "\u05e1\u05d5\u05db\u05e0\u05d9\u05dd"
        ]

        if any(x in q for x in agent_terms):
            name_terms = [
                "name",
                "names",
                "\u05e9\u05dd",
                "\u05e9\u05de\u05d5\u05ea"
            ]

            if any(x in q for x in name_terms):
                names = [
                    a.get("name", "?")
                    for a in agents.values()
                ]
                return "Agents names: " + ", ".join(names)

            return f"Agents count={len(agents)}"

        context = f"""
SLH SYSTEM STATE:

User:
name={user.get("name")}
role={user.get("role")}
credits={user.get("wallet", {}).get("credits", 0)}

Agents:
count={len(agents)}
names={", ".join([a.get("name", "?") for a in agents.values()])}
"""

    except Exception as e:
        context = f"Context error: {e}"

    prompt = f"""
You are SLH OS AI assistant.
Answer in Hebrew, concise and direct.

IMPORTANT SYSTEM RULES:
- SYSTEM CONTEXT is the only source of truth.
- Previous conversation messages are NOT system data.
- Never guess system values.
- Never invent names, numbers, balances, roles, or agent counts.
- If a requested system fact is not present, say it is unknown.

SYSTEM CONTEXT:
{context}

USER QUESTION:
{question}
"""

    return ask_groq(prompt)

def register(bot):
    return register_llm_handler(bot)

print('LLM MODULE LOADED FROM:', __file__)

