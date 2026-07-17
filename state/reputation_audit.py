import json
import time

AUDIT_FILE = "state/reputation_audit.json"


def load_audit():
    try:
        with open(AUDIT_FILE) as f:
            return json.load(f)
    except:
        return []


def save_audit(data):
    with open(AUDIT_FILE, "w") as f:
        json.dump(data, f, indent=2)


def record_reward(admin_id, user_id, action):
    audit = load_audit()

    audit.append({
        "admin_id": str(admin_id),
        "user_id": str(user_id),
        "action": action,
        "time": time.time()
    })

    save_audit(audit)
