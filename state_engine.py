import os, json
from datetime import datetime

STATE_FILE = "state/system.json"

def load():
    if os.path.exists(STATE_FILE):
        try:
            return json.load(open(STATE_FILE))
        except:
            return {}
    return {}

def save(s):
    os.makedirs("state", exist_ok=True)
    json.dump(s, open(STATE_FILE, "w"), indent=2)

def set_token(token):
    s = load()
    s["BOT_TOKEN"] = token
    s["updated"] = datetime.now().isoformat()
    save(s)

def get_token():
    return load().get("BOT_TOKEN")
