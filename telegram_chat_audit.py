import os
import json
import requests

def load_token():
    if os.getenv("BOT_TOKEN"):
        return os.getenv("BOT_TOKEN")

    try:
        with open("config.json") as f:
            return json.load(f).get("BOT_TOKEN")
    except:
        return None

token = load_token()

if not token:
    print("❌ BOT_TOKEN missing")
    exit()

url = f"https://api.telegram.org/bot{token}/getUpdates"

r = requests.get(url, timeout=20)
data = r.json()

print("===== TELEGRAM CHAT AUDIT =====")

seen = {}

for item in data.get("result", []):
    msg = item.get("message") or item.get("edited_message")

    if not msg:
        continue

    chat = msg.get("chat", {})

    cid = chat.get("id")
    ctype = chat.get("type")
    title = chat.get("title", chat.get("username", "private"))

    seen[str(cid)] = {
        "id": cid,
        "type": ctype,
        "title": title
    }

for c in seen.values():
    print(c)

print()
print("TOTAL CHATS:", len(seen))
