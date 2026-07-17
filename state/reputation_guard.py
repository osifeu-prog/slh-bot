import json
import hashlib
import time

EVENT_FILE = "state/reputation_events.json"


def load_events():
    with open(EVENT_FILE) as f:
        return json.load(f)


def save_events(events):
    with open(EVENT_FILE, "w") as f:
        json.dump(events, f, indent=2)


def create_event_id(user_id, action, evidence):
    raw = f"{user_id}:{action}:{evidence}"
    return hashlib.sha256(raw.encode()).hexdigest()


def already_rewarded(event_id):
    events = load_events()

    for event in events:
        if event.get("event_id") == event_id:
            return True

    return False


def register_event(event_id):
    events = load_events()

    events.append({
        "event_id": event_id,
        "time": time.time()
    })

    save_events(events)
