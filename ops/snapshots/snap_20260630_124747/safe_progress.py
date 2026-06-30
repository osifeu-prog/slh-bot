import json, os
from datetime import datetime

STATE_FILE = "state/progress.json"

def load():
    if os.path.exists(STATE_FILE):
        try:
            return json.load(open(STATE_FILE))
        except:
            return {}
    return {}

def save(data):
    os.makedirs("state", exist_ok=True)
    json.dump(data, open(STATE_FILE, "w"), indent=2)

def enroll_user(user_id, course):
    db = load()
    uid = str(user_id)

    if uid not in db:
        db[uid] = {}

    if course in db[uid]:
        return False

    db[uid][course] = {
        "current_stage": 1,
        "completed": [],
        "created": datetime.now().isoformat()
    }

    save(db)
    return True

def get_progress(user_id):
    db = load()
    return db.get(str(user_id), {})
