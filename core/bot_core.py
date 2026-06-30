import json, time, requests, os, atexit

LOCK = "slh.lock"

if os.path.exists(LOCK):
    print("❌ already running")
    exit()

open(LOCK, "w").write(str(os.getpid()))

def cleanup():
    try:
        os.remove(LOCK)
    except:
        pass

atexit.register(cleanup)

token = json.load(open("config.json"))["BOT_TOKEN"]
BASE = f"https://api.telegram.org/bot{token}"

db = json.load(open("db.json"))

def save_db():
    with open("db.json","w") as f:
        json.dump(db,f,indent=2)

def get_updates(offset):
    return requests.get(
        BASE + "/getUpdates",
        params={"timeout": 20, "offset": offset},
        timeout=30
    ).json()

def send(chat_id, text):
    requests.post(BASE + "/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=30
    )

print("🚀 SLH v4 RUNNING")

offset = db.get("offset", 0)

while True:
    try:
        data = get_updates(offset)

        if not data.get("ok"):
            time.sleep(2)
            continue

        for u in data["result"]:
            offset = u["update_id"] + 1
            db["offset"] = offset

            msg = u.get("message", {})
            text = msg.get("text","")
            chat_id = msg.get("chat", {}).get("id")

            if not chat_id:
                continue

            # CORE COMMANDS
            if text == "/start":
                send(chat_id, "🚀 SLH v4 ONLINE")

            elif text == "/status":
                send(chat_id, "🟢 SYSTEM OK")

            elif text == "/ping":
                send(chat_id, "pong 🟢")

        save_db()

    except Exception as e:
        print("⚠️ error:", e)
        time.sleep(3)
