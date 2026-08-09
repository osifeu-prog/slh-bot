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
    return {
        "commit": os.getenv(
            "RAILWAY_GIT_COMMIT_SHA",
            os.getenv("COMMIT_SHA", "unknown")
        ),
        "branch": os.getenv(
            "RAILWAY_GIT_BRANCH",
            os.getenv("BRANCH", "unknown")
        ),
        "environment": os.getenv(
            "RAILWAY_ENVIRONMENT",
            "production"
        ),
        "deployment_id": os.getenv(
            "RAILWAY_DEPLOYMENT_ID",
            "unknown"
        )
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
