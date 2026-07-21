import os, json

def _get_missions_summary():
    board = "state/missions/board.json"
    if not os.path.exists(board):
        return "אין נתוני משימות."
    try:
        with open(board, "r", encoding="utf-8") as f:
            data = json.load(f)
        missions = data.get("missions", [])
        if not missions:
            return "אין משימות כרגע."
        lines = ["משימות אחרונות:"]
        for m in missions[-20:]:
            status = m.get("status", "?")
            agent = m.get("assigned_to") or "לא שויך"
            lines.append(f"#{m['id']} [{status}] {m['desc']} (אחראי: {agent})")
        return "\n".join(lines)
    except Exception as e:
        return f"שגיאה בטעינת משימות: {e}"

def _count_from_file(path, key=None):
    if not os.path.exists(path):
        return 0
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if key:
            return len(data.get(key, {}))
        else:
            return len(data) if isinstance(data, (dict, list)) else 0
    except:
        return 0

def get_context():
    ctx = {
        "system": "SLH OS",
        "status": "online",
        "users": 0,
        "agents": 0,
        "tasks": 0,
        "last_error": None,
        "missions_summary": _get_missions_summary()
    }

    ctx["users"] = _count_from_file("state/db.json", "users")
    ctx["tasks"] = _count_from_file("state/db.json", "tasks")
    ctx["agents"] = _count_from_file("state/agents.json")

    return ctx
