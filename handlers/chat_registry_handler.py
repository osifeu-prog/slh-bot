import json
import os
import time

FILE = "state/chats.json"


def load():
    if os.path.exists(FILE):
        try:
            with open(FILE) as f:
                return json.load(f)
        except:
            pass
    return {}


def save(data):
    os.makedirs("state", exist_ok=True)
    with open(FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def register(bot):

    original_send = bot.send_message

    def wrapped_send(chat_id, *args, **kwargs):
        try:
            chats = load()

            chats[str(chat_id)] = {
                "id": chat_id,
                "type": "known",
                "updated": time.time()
            }

            save(chats)

        except Exception as e:
            print("chat registry save error:", e)

        return original_send(chat_id, *args, **kwargs)

    bot.send_message = wrapped_send

    print("💬 Chat registry active")
