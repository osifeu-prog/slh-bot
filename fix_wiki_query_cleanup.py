path = "advanced_ask_handler.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

old = '''def _get_wikipedia_source(query):
    headers = {"User-Agent": "SLH-OS-Bot/1.0 (https://t.me/Me_ad_main_bot)"}
    for lang in ("he", "en"):'''

new = '''def _clean_wiki_query(query):
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
    for lang in ("he", "en"):'''

if old not in content:
    print("ERROR: function start not found, aborting")
    raise SystemExit(1)
content = content.replace(old, new)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("Fix applied successfully")
