import json
import os
import subprocess
from datetime import datetime


def _load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def get_deployment_state():
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True
        ).strip()
    except Exception:
        commit = "unknown"

    try:
        branch = subprocess.check_output(
            ["git", "branch", "--show-current"],
            text=True
        ).strip()
    except Exception:
        branch = "unknown"

    return {
        "commit": commit,
        "branch": branch
    }


def get_system_snapshot():
    db = _load_json(
        "state/db.json",
        {}
    )

    ai = _load_json(
        "state/ai_health.json",
        {}
    )

    agents = db.get("agents", {})
    users = db.get("users", {})

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "system": {
            "status": "online"
        },
        "users": {
            "count": len(users)
        },
        "agents": {
            "count": len(agents),
            "active": len([
                a for a in agents.values()
                if a.get("state") == "active"
            ])
        },
        "ai": ai,
        "deployment": get_deployment_state()
    }
