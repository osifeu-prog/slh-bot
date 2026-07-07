path = "advanced_ask_handler.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

# Add wikipedia helper function right after _get_api_key/_set_current_provider
old_helpers_end = '''def _set_current_provider():
    global current_provider
    for prov in PROVIDERS:
        if _get_api_key(prov):
            current_provider = prov
            return prov
    return None'''

new_helpers_end = '''def _set_current_provider():
    global current_provider
    for prov in PROVIDERS:
        if _get_api_key(prov):
            current_provider = prov
            return prov
    return None

def _get_wikipedia_source(query):
    for lang in ("he", "en"):
        try:
            resp = requests.get(
                f"https://{lang}.wikipedia.org/w/api.php",
                params={"action": "opensearch", "search": query, "limit": 1, "namespace": 0, "format": "json"},
                timeout=8
            )
            if resp.status_code == 200:
                data = resp.json()
                if len(data) >= 4 and data[1] and data[3]:
                    return data[1][0], data[3][0]
        except Exception:
            continue
    return None, None'''

if old_helpers_end not in content:
    print("ERROR: helpers block not found, aborting")
    raise SystemExit(1)
content = content.replace(old_helpers_end, new_helpers_end)

# Add credit check + deduction + wikipedia source to ask()
old_ask_start = '''        question = parts[1]

        global current_provider
        available = [p for p in PROVIDERS if _get_api_key(p)]'''

new_ask_start = '''        question = parts[1]

        import state_manager
        from admin_utils import is_admin
        uid_str = str(m.from_user.id)
        db = state_manager.load_db()
        user = db.get("users", {}).get(uid_str, {})
        credits = user.get("ask_credits", 0)
        admin = is_admin(m)
        if not admin and credits <= 0:
            bot.reply_to(m, "❌ No ask credits left. Use /buy ask_credit to get more.")
            return

        global current_provider
        available = [p for p in PROVIDERS if _get_api_key(p)]'''

if old_ask_start not in content:
    print("ERROR: ask() start block not found, aborting")
    raise SystemExit(1)
content = content.replace(old_ask_start, new_ask_start)

old_success = '''                if len(answer) > 4000:
                    answer = answer[:4000] + "..."
                bot.reply_to(m, f"🧠 [{prov}] {answer}")
                current_provider = prov
                return'''

new_success = '''                if len(answer) > 4000:
                    answer = answer[:4000] + "..."

                title, wiki_url = _get_wikipedia_source(question)
                if wiki_url:
                    answer += f"\\n\\n📖 מקור: [{title}]({wiki_url})"

                if not admin:
                    db2 = state_manager.load_db()
                    u2 = db2.setdefault("users", {}).setdefault(uid_str, {"balance": 0, "ask_credits": 0})
                    u2["ask_credits"] = max(0, u2.get("ask_credits", 0) - 1)
                    state_manager.save_db(db2)

                bot.reply_to(m, f"🧠 [{prov}] {answer}", parse_mode="Markdown")
                current_provider = prov
                return'''

if old_success not in content:
    print("ERROR: success block not found, aborting")
    raise SystemExit(1)
content = content.replace(old_success, new_success)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("All 3 fixes applied successfully")
