import os, requests, state_manager
from handlers.llm_handler import get_bot_context

PROVIDERS = {
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
    }
}

current_provider = None

def _get_api_key(provider):
    key_name = PROVIDERS[provider]["key_env"]
    # try environment first
    key = os.environ.get(key_name, '')
    if key:
        return key
    # fallback to config.json
    try:
        import json
        with open('config.json', 'r') as cf:
            cfg = json.load(cf)
        return cfg.get(key_name, '')
    except:
        return ''

def _set_current_provider():
    global current_provider
    for prov in PROVIDERS:
        if _get_api_key(prov):
            current_provider = prov
            return prov
    return None

def _clean_wiki_query(query):
    import re
    q = query.strip().rstrip("?!.")
    prefixes = [
        "מה זה", "מה זו", "מה הם", "מה הן", "מהי", "מהו",
        "מי זה", "מי זו", "מי הם", "מי הן",
        "תסביר לי על", "תסביר על", "ספר לי על", "ספר על",
        "what is", "what are", "who is", "who are", "tell me about", "explain"
    ]
    q_lower = q.lower()
    for p in prefixes:
        if q_lower.startswith(p.lower()):
            q = q[len(p):].strip()
            break
    return q if q else query.strip()

def _get_wikipedia_source(query):
    query = _clean_wiki_query(query)
    headers = {"User-Agent": "SLH-OS-Bot/1.0 (https://t.me/Me_ad_main_bot)"}
    for lang in ("he", "en"):
        try:
            resp = requests.get(
                f"https://{lang}.wikipedia.org/w/api.php",
                params={"action": "opensearch", "search": query, "limit": 1, "namespace": 0, "format": "json"},
                headers=headers,
                timeout=8
            )
            if resp.status_code == 200:
                data = resp.json()
                if len(data) >= 4 and data[1] and data[3]:
                    return data[1][0], data[3][0]
        except Exception:
            continue
    return None, None

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
        print("DEBUG m.text =", repr(m.text))
        uid = str(m.from_user.id)
        parts = m.text.split(maxsplit=1)
        print("DEBUG parts =", parts)
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /ask <your question>")
            return
        question = parts[1]

        from admin_utils import is_admin
        import state_manager
        uid_str = str(m.from_user.id)
        # Load SLH context only for system-related questions
        slh_keywords = [
            "slh", "system", "מערכת", "משתמש", "משתמשים",
            "קורס", "קורסים", "משימה", "משימות",
            "agent", "agents", "סוכן", "סוכנים",
            "progress", "התקדמות", "wallet", "ארנק",
            "credit", "credits", "staking", "marketplace"
        ]

        is_slh_question = any(
            k.lower() in question.lower()
            for k in slh_keywords
        )

        context = get_bot_context(uid_str) if is_slh_question else ""

        db = state_manager.load_db()
        user = db.get("users", {}).get(uid_str, {})
        credits = user.get("ask_credits", 0)
        admin = is_admin(m)
        if not admin and credits <= 0:
            bot.reply_to(m, "❌ No ask credits left. Use /buy ask_credit to get more.")
            return

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
                    payload = {
    "contents": [
        {
            "parts": [
                {
                    "text": SLH_SYSTEM_PROMPT + "\n\nSYSTEM CONTEXT:\n" + context + "\n\nUSER QUESTION:\n" + question
                }
            ]
        }
    ]
}
                    resp = requests.post(url_with_key, json=payload, timeout=15)
                    if resp.status_code == 200:
                        data = resp.json()
                        answer = data["candidates"][0]["content"]["parts"][0]["text"]
                    else:
                        errors.append(f"{prov}: HTTP {resp.status_code}")
                        continue
                else:
                    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
                    payload = {
    "model": model,
    "messages": [
        {
            "role": "system",
            "content": SLH_SYSTEM_PROMPT + "\n\nSYSTEM CONTEXT:\n" + context
        },
        {
            "role": "user",
            "content": question
        }
    ],
    "max_tokens": 1200,
    "temperature": 0.7
}
                    print("DEBUG GROQ REQUEST UTF8")
                    resp = requests.post(url, json=payload, headers=headers, timeout=15)
                    if resp.status_code == 200:
                        data = resp.json()
                        answer = data["choices"][0]["message"]["content"].strip()
                        print("DEBUG GROQ ANSWER OK")
                    else:
                        errors.append(f"{prov}: HTTP {resp.status_code}")
                        continue

                if len(answer) > 4000:
                    answer = answer[:4000] + "..."

                # Wikipedia auto-source disabled:
                # avoid attaching unrelated pages to general LLM answers

                if not admin:
                    db2 = state_manager.load_db()
                    u2 = db2.setdefault("users", {}).setdefault(uid_str, {"balance": 0, "ask_credits": 0})
                    u2["ask_credits"] = max(0, u2.get("ask_credits", 0) - 1)
                    state_manager.save_db(db2)

                print("DEBUG BEFORE TELEGRAM REPLY")
                print("CHAT ID:", m.chat.id)
                bot.send_message(m.chat.id, f"🧠 ({prov})\n{answer}")
                print("DEBUG AFTER TELEGRAM SEND")
                current_provider = prov
                return
            except Exception as e:
                import traceback
                print("===== LLM EXCEPTION =====")
                traceback.print_exc()
                print("===== END LLM EXCEPTION =====")
                errors.append(f"{prov}: {e}")
                continue

        current_provider = None
        bot.reply_to(m, "❌ All LLM providers failed:\n" + "\n".join(errors))

# SLH System Prompt (patched)
SLH_SYSTEM_PROMPT = """אתה עוזר AI כללי.
ענה בעברית טבעית ותמציתית.
אל תקשר תשובות כלליות ל-SLH OS אלא אם המשתמש שאל במפורש על SLH או על המערכת.

כאשר מצורף SYSTEM CONTEXT של SLH OS:
השתמש בו כמקור אמת פנימי.
אל תמציא נתונים.
ענה ישירות על שאלות הקשורות למערכת."""
