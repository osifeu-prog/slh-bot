path = "advanced_ask_handler.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

# Fix 1: reorder providers so Groq is tried first (Gemini is currently quota-limited)
old_providers = '''PROVIDERS = {
    "gemini": {
        "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
        "model": None,
        "key_env": "GEMINI_API_KEY"
    },
    "groq": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "model": "llama-3.1-8b-instant",
        "key_env": "GROQ_API_KEY"
    },
    "openai": {
        "url": "https://api.openai.com/v1/chat/completions",
        "model": "gpt-3.5-turbo",
        "key_env": "OPENAI_API_KEY"
    }'''

new_providers = '''PROVIDERS = {
    "groq": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "model": "llama-3.1-8b-instant",
        "key_env": "GROQ_API_KEY"
    },
    "gemini": {
        "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
        "model": None,
        "key_env": "GEMINI_API_KEY"
    },
    "openai": {
        "url": "https://api.openai.com/v1/chat/completions",
        "model": "gpt-3.5-turbo",
        "key_env": "OPENAI_API_KEY"
    }'''

if old_providers not in content:
    print("ERROR: PROVIDERS block not found, aborting")
    raise SystemExit(1)
content = content.replace(old_providers, new_providers)

# Fix 2: add real fallback loop across all available providers
old_ask = '''    @bot.message_handler(commands=['ask'])
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
            bot.reply_to(m, "❌ No LLM provider configured. Set an API key and try /llm_provider.")
            return

        key = _get_api_key(prov)
        url = PROVIDERS[prov]["url"]
        model = PROVIDERS[prov]["model"]

        try:
            if prov == "gemini":
                url_with_key = f"{url}?key={key}"
                payload = {"contents": [{"parts": [{"text": question}]}]}
                resp = requests.post(url_with_key, json=payload, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    answer = data["candidates"][0]["content"]["parts"][0]["text"]
                else:
                    bot.reply_to(m, f"❌ Gemini error: {resp.status_code} {resp.text[:200]}")
                    return
            else:
                headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
                payload = {"model": model, "messages": [{"role": "user", "content": question}], "max_tokens": 500, "temperature": 0.7}
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
            bot.reply_to(m, f"❌ Error: {e}")'''

new_ask = '''    @bot.message_handler(commands=['ask'])
    def ask(m):
        uid = str(m.from_user.id)
        parts = m.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /ask <your question>")
            return
        question = parts[1]

        global current_provider
        available = [p for p in PROVIDERS if _get_api_key(p)]
        if not available:
            bot.reply_to(m, "❌ No LLM provider configured. Set an API key and try /llm_provider.")
            return

        if not current_provider or current_provider not in available:
            _set_current_provider()
        ordered = [current_provider] + [p for p in available if p != current_provider] if current_provider in available else available

        errors = []
        for prov in ordered:
            key = _get_api_key(prov)
            url = PROVIDERS[prov]["url"]
            model = PROVIDERS[prov]["model"]
            try:
                if prov == "gemini":
                    url_with_key = f"{url}?key={key}"
                    payload = {"contents": [{"parts": [{"text": question}]}]}
                    resp = requests.post(url_with_key, json=payload, timeout=15)
                    if resp.status_code == 200:
                        data = resp.json()
                        answer = data["candidates"][0]["content"]["parts"][0]["text"]
                    else:
                        errors.append(f"{prov}: HTTP {resp.status_code}")
                        continue
                else:
                    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
                    payload = {"model": model, "messages": [{"role": "user", "content": question}], "max_tokens": 500, "temperature": 0.7}
                    resp = requests.post(url, json=payload, headers=headers, timeout=15)
                    if resp.status_code == 200:
                        data = resp.json()
                        answer = data["choices"][0]["message"]["content"].strip()
                    else:
                        errors.append(f"{prov}: HTTP {resp.status_code}")
                        continue

                if len(answer) > 4000:
                    answer = answer[:4000] + "..."
                bot.reply_to(m, f"🧠 [{prov}] {answer}")
                current_provider = prov
                return
            except Exception as e:
                errors.append(f"{prov}: {e}")
                continue

        current_provider = None
        bot.reply_to(m, "❌ All LLM providers failed:\\n" + "\\n".join(errors))'''

if old_ask not in content:
    print("ERROR: ask() block not found, aborting")
    raise SystemExit(1)
content = content.replace(old_ask, new_ask)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("Both fixes applied successfully")
