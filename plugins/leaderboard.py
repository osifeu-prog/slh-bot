import json
import os

DB = "db.json"

def load():
    if not os.path.exists(DB):
        return {"users": {}}
    return json.load(open(DB))

def handle(text, chat_id, user_id, send):
    db = load()

    if text == "/top":
        users = db.get("users", {})
        ranked = sorted(users.items(), key=lambda x: x[1].get("coins",0), reverse=True)

        msg = "🏆 TOP USERS:\n"
        for i,(uid,data) in enumerate(ranked[:5]):
            msg += f"{i+1}. {uid} - {data.get('coins',0)} coins\n"

        send(chat_id, msg)
