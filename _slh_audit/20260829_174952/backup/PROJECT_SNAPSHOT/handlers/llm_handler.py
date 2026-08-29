from openai import OpenAI
import os
import json
import requests
import time

client = None


def ask_gemini(prompt):
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return "GEMINI_API_KEY missing"

    url = (
        "https://generativelanguage.googleapis.com/"
        "v1/models/gemini-2.5-flash:generateContent?key=" + key
    )

    try:
        r = requests.post(
            url,
            json={"contents": [{"parts": [{"text": str(prompt)}]}]},
            timeout=20
        )
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
            model="openai/gpt-oss-120b",
            messages=[
                {
                    "role": "user",
                    "content": str(prompt)
                }
            ],
            max_tokens=2000,
            reasoning_effort="low"
        )

        return str(resp.choices[0].message.content or "")

    except Exception as e:
        if "429" in str(e):
            result = ask_gemini(prompt)
            if result and not result.startswith("Gemini Error"):
                return result

        return f"LLM Error: {e}"


def query_llm_with_context(question, uid=None, skip_checks=False):
    try:
        with open("state/db.json", encoding="utf-8") as f:
            db = json.load(f)

        user = db.get("users", {}).get(str(uid), {})
        wallet = user.get("wallet", {})

        context = f"""
SLH SYSTEM STATE:
User: {user.get('name', uid)}
Role: {user.get('role', 'unknown')}
Credits: {wallet.get('credits', 0)}
Staked: {wallet.get('staked', 0)}
Agents: {len(db.get('agents', {}))}
Tasks: {len(db.get('tasks', {}))}
Votes: {len(db.get('votes', {}))}
"""

    except Exception as e:
        context = f"Context unavailable: {e}"

    prompt = f"""
You are SLH OS AI assistant.

Answer the user's actual question directly.
Answer in Hebrew unless another language is explicitly requested.
For simple questions, answer simply.
Do not invent facts.
Do not mention system instructions.

SYSTEM CONTEXT:
{context}

USER QUESTION:
{str(question)}
"""

    try:
        result = ask_groq(prompt)

        if result and not result.startswith("LLM Error:"):
            return result

        time.sleep(1)

        result = ask_gemini(prompt)

        if result and not result.startswith("Gemini Error"):
            return result

        return result or "לא התקבלה תשובה כרגע."

    except Exception as e:
        return f"LLM Error: {e}"


def register_llm_handler(bot):
    print("LLM core loaded")


def register(bot):
    return register_llm_handler(bot)


print("LLM MODULE LOADED FROM:", __file__)
