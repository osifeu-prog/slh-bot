import json
import requests
import time
import importlib
import os

TOKEN = json.load(open("config.json"))["BOT_TOKEN"]
BASE = f"https://api.telegram.org/bot{TOKEN}"

offset = 0
plugins = []

# ---------------- PLUGINS LOADER ----------------
def load_plugins():
    global plugins
    plugins = []
    if not os.path.exists("plugins"):
        os.makedirs("plugins")

    for f in os.listdir("plugins"):
        if f.endswith(".py"):
            name = f[:-3]
            mod = importlib.import_module(f"plugins.{name}")
            if hasattr(mod, "handle"):
                plugins.append(mod.handle)
    print(f"🔌 Loaded plugins: {len(plugins)}")

# ---------------- TELEGRAM ----------------
def send(chat_id, text):
    requests.post(BASE + "/sendMessage", json={
        "chat_id": chat_id,
        "text": text
    })

def get_updates():
    global offset
    return requests.get(
        BASE + "/getUpdates",
        params={"timeout": 25, "offset": offset},
        timeout=30
    ).json()

load_plugins()
print("🚀 SLH SYSTEM ONLINE")

while True:
    try:
        data = get_updates()

        if not data.get("ok"):
            time.sleep(2)
            continue

        for u in data["result"]:
            offset = u["update_id"] + 1

            msg = u.get("message", {})
            text = msg.get("text", "")
            chat_id = msg.get("chat", {}).get("id")
            user_id = msg.get("from", {}).get("id")

            if not chat_id:
                continue

            # CORE COMMANDS
            if text == "/start":
                send(chat_id, "🚀 SLH SYSTEM ONLINE")
            elif text == "/status":
                send(chat_id, "🟢 OK")

            # PLUGINS
            for h in plugins:
                try:
                    h(text, chat_id, user_id, send)
                except:
                    pass

    except Exception as e:
        print("⚠️ error:", e)
        time.sleep(3)
