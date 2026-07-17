import json
import time
from pathlib import Path

REP_FILE = Path("state/reputation.json")
EVENT_FILE = Path("state/reputation_events.json")


def load_reputation():
    if not REP_FILE.exists():
        return {}
    with open(REP_FILE) as f:
        return json.load(f)


def save_reputation(data):
    with open(REP_FILE, "w") as f:
        json.dump(data, f, indent=2)


def load_events():
    if not EVENT_FILE.exists():
        return []
    with open(EVENT_FILE) as f:
        return json.load(f)


def save_events(data):
    with open(EVENT_FILE, "w") as f:
        json.dump(data, f, indent=2)


def add_reputation(user_id, action, points):
    reputation = load_reputation()
    events = load_events()

    uid = str(user_id)

    if uid not in reputation:
        reputation[uid] = {
            "score": 0,
            "level": "new",
            "history": []
        }

    reputation[uid]["score"] += points
    reputation[uid]["history"].append({
        "action": action,
        "points": points,
        "time": time.time()
    })

    events.append({
        "user_id": uid,
        "action": action,
        "points": points,
        "time": time.time()
    })

    save_reputation(reputation)
    save_events(events)

    return reputation[uid]


def get_reputation(user_id):
    reputation = load_reputation()
    return reputation.get(str(user_id), None)
