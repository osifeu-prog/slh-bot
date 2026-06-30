import json
import os

DB = "db.json"

def load():
    if not os.path.exists(DB):
        return {"users": {}}
    return json.load(open(DB))

def save(db):
    json.dump(db, open(DB, "w"), indent=2)

def handle(text, chat_id, user_id, send):
    db = load()
    uid = str(user_id)

    if uid not in db["users"]:
        db["users"][uid] = {"coins": 10}

    if text == "/shop":
        send(chat_id, "🛒 SHOP:\n1. VIP - 10 coins\n2. BOOST - 5 coins")

    elif text == "/coins":
        send(chat_id, f"💰 Coins: {db['users'][uid]['coins']}")
        save(db)
