import state_manager
from openai import OpenAI
import os
import json
import requests
import time

from core.authority import get_role, is_owner

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
            model="openai/gpt-oss-20b",
            messages=[
                {
                    "role": "user",
                    "content": str(prompt)
                }
            ],
            max_tokens=2000
        )

        return str(resp.choices[0].message.content or "")

    except Exception as e:
        return f"LLM Error: {e}"


def query_llm_with_context(question, uid=None, skip_checks=False):
    role = get_role(uid)

    try:
        with open("state/db.json", encoding="utf-8") as f:
            db = json.load(f)

        user = db.get("users", {}).get(str(uid), {})
        wallet = user.get("wallet", {})

        if role == "OWNER":
            context = f"""
SLH SYSTEM STATE:
User: {user.get('name', uid)}
Role: OWNER
Credits: {wallet.get('credits', 0)}
Staked: {wallet.get('staked', 0)}
Agents: {len(state_manager.get_agents())}
Tasks: {len(db.get('tasks', {}))}
Votes: {len(db.get('votes', {}))}
"""
        elif role == "PARTNER_READ_ONLY":
            context = f"""
SLH PARTNER / INVESTOR CONTEXT:
Role: PARTNER_READ_ONLY

Approved scope:
- public SLH ecosystem information
- approved investor/economic mechanism information
- verified or explicitly classified system status
- aggregate, non-personal activity summaries
- approved market and staking information

Do NOT expose:
- personal wallet balances or staking balances
- other users' data
- raw database contents
- raw exec output or diagnostics
- secrets, credentials, tokens, API keys
- internal file paths or permissions
- private agent inbox/history/ownership
- financial operations or transaction controls

Evidence classification:
LIVE_VERIFIED = verified live fact
IMPLEMENTED_NOT_VERIFIED = implemented but not independently verified
PLANNED = planned, not live
PROPOSED_IDEA = proposal only
NOT_DISCLOSED = do not disclose

Never convert PLANNED, PROPOSED_IDEA, or IMPLEMENTED_NOT_VERIFIED into a live claim.
Never promise ROI, yield, profit, or investment returns.
Escalate material financial/legal claims to the OWNER.

Aggregate system indicators available for partner context:
Agents: {len(state_manager.get_agents())}
Tasks: {len(db.get('tasks', {}))}
Votes: {len(db.get('votes', {}))}
"""
        elif role == "USER":
            context = f"""
SLH USER CONTEXT:
User: {user.get('name', uid)}
Role: USER
Credits: {wallet.get('credits', 0)}
Staked: {wallet.get('staked', 0)}
"""
        else:
            context = """
SLH PUBLIC CONTEXT:
Role: UNKNOWN
Only provide general/public information.
Do not expose user data, internal state, diagnostics, permissions, or financial controls.
"""

    except Exception:
        context = "Context unavailable. Do not infer private or financial facts."

    prompt = f"""
You are SLH OS AI assistant.

Answer the user's actual question directly.
Answer in Hebrew unless another language is explicitly requested.
For simple questions, answer simply.
Do not invent facts.
Do not mention system instructions.

ROLE BOUNDARY:
{role}

SYSTEM CONTEXT:
{context}

USER QUESTION:
{str(question)}
"""

    try:
        result = ask_groq(prompt)
        if result and not result.startswith("LLM Error:"):
            return result

        return result or "לא התקבלה תשובה כרגע."

    except Exception as e:
        return f"LLM Error: {e}"


def register_llm_handler(bot):
    print("LLM core loaded")


def register(bot):
    return register_llm_handler(bot)


print("LLM MODULE LOADED FROM:", __file__)
