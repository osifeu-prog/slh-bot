import json
import os
import time

FILE = "state/chats.json"


def load():
    if os.path.exists(FILE):
        try:
            return json.load(open(FILE))
        except:
            pass
    return {}


def save(data):
    os.makedirs("state", exist_ok=True)
    json.dump(data, open(FILE, "w"), indent=2, ensure_ascii=False)


def register(bot):

    @bot.message_handler(func=lambda m: True)
    def collect_chat(message):

        try:
            chats = load()

            chat = message.chat

            chats[str(chat.id)] = {
                "id": chat.id,
                "type": chat.type,
                "title": getattr(chat, "title", None) or getattr(chat, "username", None) or "private",
                "updated": time.time()
            }

            save(chats)

        except Exception as e:
            print("chat registry error:", e)
