import json, time
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path("state/db.json")
WORK_LOG_PATH = Path("state/work_log.json")

def _load_db():
    return json.loads(DB_PATH.read_text(encoding="utf-8"))

def get_progress():
    db = _load_db()
    users = len(db.get("users", {}))
    agents = len(db.get("agents", {}))
    tasks = len(db.get("tasks", {}))
    ledger = len(db.get("ledger", []))

    checks = [
        ("Infrastructure", 90 if DB_PATH.exists() else 0),
        ("Runtime", 90 if Path("bot_gateway.py").exists() else 0),
        ("Identity", 80 if users >= 1 else 0),
        ("Wallet", 80 if users > 0 else 0),
        ("Economy authority", 70 if ledger > 0 else 0),
        ("Store", 45 if Path("handlers/store_handler.py").exists() else 0),
        ("Real user journey", 35 if users > 0 and agents > 0 else 0),
        ("AI Agents", 75 if agents >= 4 else 0),
        ("Security", 85 if Path("handlers/firewall_handler.py").exists() else 0),
        ("Ledger Integrity", 100 if ledger > 0 else 0),
    ]
    return checks

def _load_work_log():
    if not WORK_LOG_PATH.exists():
        return []
    try:
        return json.loads(WORK_LOG_PATH.read_text(encoding="utf-8"))
    except:
        return []

def start_work(task_name, user_id):
    log = _load_work_log()
    log.append({
        "task": task_name,
        "user": str(user_id),
        "start": datetime.now(timezone.utc).isoformat(),
        "stop": None
    })
    WORK_LOG_PATH.write_text(json.dumps(log, indent=2, ensure_ascii=False))
    return True

def stop_work(task_name, user_id):
    log = _load_work_log()
    now = datetime.now(timezone.utc).isoformat()
    updated = False
    for entry in reversed(log):
        if entry.get("task") == task_name and entry.get("user") == str(user_id) and entry.get("stop") is None:
            entry["stop"] = now
            updated = True
            break
    WORK_LOG_PATH.write_text(json.dumps(log, indent=2, ensure_ascii=False))
    return updated

def get_work_log(user_id=None):
    log = _load_work_log()
    if user_id is not None:
        log = [x for x in log if x.get("user") == str(user_id)]
    return log

def progress_report():
    lines = ["📊 SLH PROGRESS", ""]
    for name, pct in get_progress():
        filled = int(pct / 10)
        bar = "█" * filled + "░" * (10 - filled)
        lines.append(f"{name:20} {bar} {pct}%")
    lines.append("")
    lines.append(f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    return "\n".join(lines)
