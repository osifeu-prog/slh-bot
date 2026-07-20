import os, sqlite3, json

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
    if os.path.exists('slh_state.db'):
        try:
            conn = sqlite3.connect('slh_state.db')
            tables = [r[0] for r in conn.execute('SELECT name FROM sqlite_master WHERE type="table"').fetchall()]
            if 'users' in tables:
                ctx['users'] = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
            if 'agents' in tables:
                ctx['agents'] = conn.execute('SELECT COUNT(*) FROM agents').fetchone()[0]
            if 'tasks' in tables:
                ctx['tasks'] = conn.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]
            conn.close()
        except:
            pass
    return ctx
