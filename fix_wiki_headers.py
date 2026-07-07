path = "advanced_ask_handler.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

old = '''def _get_wikipedia_source(query):
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

new = '''def _get_wikipedia_source(query):
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
    return None, None'''

if old not in content:
    print("ERROR: wikipedia function not found, aborting")
    raise SystemExit(1)
content = content.replace(old, new)

old_reply = 'bot.reply_to(m, f"🧠 [{prov}] {answer}", parse_mode="Markdown")'
new_reply = 'bot.reply_to(m, f"🧠 ({prov})\\n{answer}", parse_mode="Markdown")'

if old_reply not in content:
    print("ERROR: reply line not found, aborting")
    raise SystemExit(1)
content = content.replace(old_reply, new_reply)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("Both fixes applied successfully")
