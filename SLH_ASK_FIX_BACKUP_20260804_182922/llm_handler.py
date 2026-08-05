from openai import OpenAI
import os

client = None

def ask_gemini(prompt):
    import requests, os
    key = os.getenv("GEMINI_API_KEY")
    if not key: return "GEMINI_API_KEY missing"
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
        if "429" in str(e): return ask_gemini(prompt)
        return f"LLM Error: {e}"


def register_llm_handler(bot):

    @bot.message_handler(commands=['ask'])
    def ask_cmd(msg):
        question = msg.text.replace('/ask', '').strip()

        if not question:
            bot.reply_to(msg, "שימוש: /ask <שאלה>")
            return

        answer = ask_groq(question)
        bot.reply_to(msg, f"?? {answer}")


def query_llm_with_context(question, uid=None):
    """
    Compatibility bridge for advanced_ask_handler.
    """

    prompt = f"""
You are SLH OS AI assistant.
Answer in Hebrew, concise and direct.

USER QUESTION:
{question}
"""

    return ask_groq(prompt)


