import json, os, threading
from datetime import datetime

LOCK_FILE = "runtime/dna.lock"
LOCK = threading.Lock()

def _load(path):
    if os.path.exists(path):
        try:
            return json.load(open(path))
        except:
            return {}
    return {}

def _save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(data, open(path, "w"), indent=2)

def acquire_lock(user_id):
    with LOCK:
        locks = _load(LOCK_FILE)

        uid = str(user_id)
        if uid in locks:
            return False

        locks[uid] = {
            "time": datetime.now().isoformat()
        }

        _save(LOCK_FILE, locks)
        return True

def release_lock(user_id):
    with LOCK:
        locks = _load(LOCK_FILE)
        uid = str(user_id)

        if uid in locks:
            del locks[uid]
            _save(LOCK_FILE, locks)

def clear_stale():
    _save(LOCK_FILE, {})
