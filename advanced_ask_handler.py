import os
import requests
import state_manager

# You can set OPENAI_API_KEY in Railway variables or state/.env
API_KEY = os.environ.get("OPENAI_API_KEY", "")
API_URL = "https://api.openai.com/v1/chat/completions"  # or compatible endpoint

def register_ask_handler(bot):
    @bot.message_handler(commands=['ask'])
    def ask(m):
        uid = str(m.from_user.id)
        parts = m.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /ask <your question>")
            return
        question = parts[1]

        # Check user balance or permissions (optional)
        # For now, allow all

        if not API_KEY:
            bot.reply_to(m, "❌ LLM API key not configured. Please set OPENAI_API_KEY.")
            return

        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": question}],
            "max_tokens": 500,
            "temperature": 0.7
        }

        try:
            resp = requests.post(API_URL, json=data, headers=headers, timeout=15)
            if resp.status_code == 200:
                answer = resp.json()["choices"][0]["message"]["content"].strip()
                # Truncate if too long
                if len(answer) > 4000:
                    answer = answer[:4000] + "..."
                bot.reply_to(m, f"🧠 {answer}")
            else:
                bot.reply_to(m, f"❌ API error: {resp.status_code} {resp.text[:200]}")
        except Exception as e:
            bot.reply_to(m, f"❌ Error: {e}")

    # Also provide a /setapikey admin command (optional, but risky)
    @bot.message_handler(commands=['setllmkey'])
    def set_llm_key(m):
        from admin_utils import is_admin
        if not is_admin(m):
            return
        parts = m.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /setllmkey <api_key>")
            return
        global API_KEY
        API_KEY = parts[1].strip()
        # Save to db for persistence? Better to use env vars.
        bot.reply_to(m, "✅ API key updated for this session. Set permanently in Railway vars.")
