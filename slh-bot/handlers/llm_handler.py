from openai import OpenAI
import os

client = None

def ask_groq(prompt):
    try:
        resp = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"LLM Error: {e}"

def register_llm_handler(bot):
    @bot.message_handler(commands=['ask'])
    def ask_cmd(msg):
        question = msg.text.replace('/ask', '').strip()
        if not question:
            bot.reply_to(msg, "שאל שאלה: /ask מה השעה")
            return
        answer = ask_groq(question)
        bot.reply_to(msg, f"🤖 {answer}")




register = register_llm_handler

def query_llm_with_context(question, uid):
    context = f"User ID: {uid}"
    prompt = f"""
You are SLH OS AI assistant.
Answer in Hebrew, concise and direct.

Context:
{context}

Question:
{question}
"""
    return ask_groq(prompt)


