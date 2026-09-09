import os
import state_manager
from openai import OpenAI
import json
import requests
from core.economy_bridge import spend_credits
from core import ask_transaction

client = None

ASK_CREDIT_COST = max(0, int(os.getenv("ASK_CREDIT_COST", "1")))


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


def _consume_paid_ask(uid, request_id):
    """Charge exactly once for this Telegram ASK request."""
    if not uid or ASK_CREDIT_COST <= 0:
        return False

    if request_id is None or not str(request_id).strip():
        return False

    idempotency_key = f"ask:{uid}:{request_id}"
    result = spend_credits(
        str(uid),
        ASK_CREDIT_COST,
        reason="ask:consume",
        meta={
            "source": "paid_ask",
            "idempotency_key": idempotency_key,
            "request_id": str(request_id),
        },
    )
    return bool(result is not False)


def _settle_saved_answer(uid, request_id, answer):
    """Settle an already persisted answer; safe to retry after a crash."""
    if not _consume_paid_ask(uid, request_id):
        return False
    ask_transaction.complete(str(uid), str(request_id))
    return True


def query_llm_with_context(
    question,
    uid=None,
    skip_checks=False,
    consume_credits=False,
    request_id=None,
):
    tx = None
    if consume_credits:
        if not uid or not str(uid).strip():
            return "⚠️ לא ניתן להפעיל בקשת AI בתשלום: מזהה משתמש חסר. נסה שוב."
        if ASK_CREDIT_COST <= 0:
            return "⚠️ מנגנון החיוב של AI אינו מוגדר. נסה שוב מאוחר יותר."
        if request_id is None or not str(request_id).strip():
            return "⚠️ לא ניתן לחייב את בקשת ה-AI: מזהה בקשה חסר. נסה שוב."

        tx_result = ask_transaction.begin_or_get(str(uid), str(request_id))
        tx = tx_result["transaction"] if tx_result else None
        if tx is None:
            return "⚠️ לא ניתן ליצור עסקת ASK. נסה שוב מאוחר יותר."

        if tx.get("status") == "COMPLETED":
            return tx.get("answer") or "לא נמצאה תשובת ASK שמורה."

        if tx.get("status") == "ANSWER_READY":
            answer = tx.get("answer") or ""
            if _settle_saved_answer(str(uid), str(request_id), answer):
                return answer
            return "⚠️ החיוב לא אושר ולכן התשובה לא נמסרה. ודא שיש לך מספיק credits ונסה שוב."

        claim = ask_transaction.claim_processing(str(uid), str(request_id))
        claimed_tx = claim.get("transaction") if claim else None
        if not claim or not claim.get("claimed"):
            if claimed_tx and claimed_tx.get("status") == "COMPLETED":
                return claimed_tx.get("answer") or "לא נמצאה תשובת ASK שמורה."
            if claimed_tx and claimed_tx.get("status") == "ANSWER_READY":
                answer = claimed_tx.get("answer") or ""
                if _settle_saved_answer(str(uid), str(request_id), answer):
                    return answer
            return "⚠️ הבקשה כבר בעיבוד. נסה שוב בעוד רגע."

        try:
            from core.economy_service import get_balance_safe
            if get_balance_safe(str(uid)) < ASK_CREDIT_COST:
                ask_transaction.fail(str(uid), str(request_id), "INSUFFICIENT_CREDITS")
                return f"אין מספיק credits לבקשת AI. נדרש: {ASK_CREDIT_COST} credit(s)."
        except Exception:
            ask_transaction.fail(str(uid), str(request_id), "BALANCE_CHECK_FAILED")
            return "⚠️ לא ניתן לאמת את יתרת ה-credits. נסה שוב מאוחר יותר."

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
Agents: {len(state_manager.get_agents())}
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
            if consume_credits:
                ask_transaction.save_answer(str(uid), str(request_id), result)
                if not _settle_saved_answer(str(uid), str(request_id), result):
                    return "⚠️ החיוב לא אושר ולכן התשובה לא נמסרה. ודא שיש לך מספיק credits ונסה שוב."
            return result

        if consume_credits:
            ask_transaction.fail(str(uid), str(request_id), result or "LLM_EMPTY")
        return result or "לא התקבלה תשובה כרגע."

    except Exception as e:
        if consume_credits:
            try:
                ask_transaction.fail(str(uid), str(request_id), str(e))
            except Exception:
                pass
        return f"LLM Error: {e}"


def register_llm_handler(bot):
    print("LLM core loaded")


def register(bot):
    return register_llm_handler(bot)


print("LLM MODULE LOADED FROM:", __file__)
