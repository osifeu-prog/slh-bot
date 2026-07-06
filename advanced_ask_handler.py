import os, requests, state_manager

# Supported LLM providers
PROVIDERS = {
    "openai": {
        "url": "https://api.openai.com/v1/chat/completions",
        "model": "gpt-3.5-turbo",
        "key_env": "OPENAI_API_KEY"
    },
    "grok": {
        "url": "https://api.x.ai/v1/chat/completions",
        "model": "grok-2-1212",
        "key_env": "GROK_API_KEY"
    },
    "gemini": {
        "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
        "model": None,
        "key_env": "GEMINI_API_KEY"
    }
}

current_provider = None

def _get_api_key(provider):
    key_name = PROVIDERS[provider]["key_env"]
    return os.environ.get(key_name, "")

def _set_current_provider():
    global current_provider
    for prov in PROVIDERS:
        if _get_api_key(prov):
            current_provider = prov
            return prov
    return None

def register_ask_handler(bot):
    @bot.message_handler(commands=['llm_provider'])
    def set_provider(m):
        from admin_utils import is_admin
        if not is_admin(m):
            bot.reply_to(m, "⛔️ Admin only")
            return
        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, f"Usage: /llm_provider {', '.join(PROVIDERS.keys())}")
            return
        choice = parts[1].lower()
        if choice not in PROVIDERS:
            bot.reply_to(m, f"Unknown provider. Choose: {', '.join(PROVIDERS.keys())}")
            return
        if not _get_api_key(choice):
            bot.reply_to(m, f"❌ API key for {choice} not set. Set {PROVIDERS[choice]['key_env']} in Railway variables.")
            return
        global current_provider
        current_provider = choice
        bot.reply_to(m, f"✅ LLM provider set to {choice}")

    @bot.message_handler(commands=['ask'])
    def ask(m):
        uid = str(m.from_user.id)
        parts = m.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /ask <your question>")
            return
        question = parts[1]

        global current_provider
        if not current_provider:
            _set_current_provider()
        prov = current_provider
        if not prov:
            bot.reply_to(m, "❌ No LLM provider configured. Set an API key (e.g., GEMINI_API_KEY) and try /llm_provider.")
            return

        key = _get_api_key(prov)
        url = PROVIDERS[prov]["url"]
        model = PROVIDERS[prov]["model"]

        try:
            if prov == "gemini":
                url_with_key = f"{url}?key={key}"
                payload = {
                    "contents": [{"parts": [{"text": question}]}]
                }
                resp = requests.post(url_with_key, json=payload, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    answer = data["candidates"][0]["content"]["parts"][0]["text"]
                else:
                    bot.reply_to(m, f"❌ Gemini error: {resp.status_code} {resp.text[:200]}")
                    return
            else:
                headers = {
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": question}],
                    "max_tokens": 500,
                    "temperature": 0.7
                }
                resp = requests.post(url, json=payload, headers=headers, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    answer = data["choices"][0]["message"]["content"].strip()
                else:
                    bot.reply_to(m, f"❌ API error ({prov}): {resp.status_code} {resp.text[:200]}")
                    return

            if len(answer) > 4000:
                answer = answer[:4000] + "..."
            bot.reply_to(m, f"🧠 [{prov}] {answer}")
        except Exception as e:
            bot.reply_to(m, f"❌ Error: {e}")
# force redeploy
