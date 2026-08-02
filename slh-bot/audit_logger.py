import json, os, time
from datetime import datetime

AUDIT_FILE = os.getenv("AUDIT_FILE", "audit.jsonl")

def audit(action, user=None, details=""):
    if user is None:
        user = "system"
    entry = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user": str(user),
        "action": action,
        "details": str(details)[:200]
    }
    with open(AUDIT_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")

def get_audit(n=20):
    if not os.path.exists(AUDIT_FILE):
        return []
    with open(AUDIT_FILE) as f:
        lines = f.readlines()
    return [json.loads(line) for line in lines[-n:]]
