import json
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "state" / "db.json"
FIREWALL_LOG = BASE_DIR / "state" / "firewall.jsonl"


def load_db():
    return json.loads(DB_PATH.read_text(encoding="utf-8-sig"))


def get_user(uid):
    db = load_db()
    return db.get("users", {}).get(str(uid), {})


def is_owner(uid):
    from security.permissions import _is_owner
    return _is_owner(uid)


def has_permission(uid, permission):
    from security.permissions import has_permission as security_has_permission
    return security_has_permission(uid, permission)


def log_deny(uid, command, reason):
    FIREWALL_LOG.parent.mkdir(parents=True, exist_ok=True)
    with FIREWALL_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "uid": str(uid),
            "command": command,
            "decision": "DENIED",
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, ensure_ascii=False) + "\n")


def require_owner(uid, command):
    if is_owner(uid):
        return True
    log_deny(uid, command, "not_owner")
    return False


def require_permission(uid, permission, command):
    if has_permission(uid, permission):
        return True
    log_deny(uid, command, f"missing_{permission}")
    return False


def firewall_status(uid):
    user = get_user(uid)
    return {
        "role": user.get("role", "none"),
        "is_owner": is_owner(uid),
        "permissions": user.get("permissions", [])
    }
