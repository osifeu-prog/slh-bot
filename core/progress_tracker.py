import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

DB_PATH = Path("state/db.json")
WORK_LOG_PATH = Path("state/work_log.json")

def _load_db():
    return json.loads(DB_PATH.read_text(encoding="utf-8"))

def get_progress():
    db = _load_db()
    tasks = db.get("tasks", {})
    checks = []
    for task_id, task in tasks.items():
        title = task.get("title", task_id)
        progress = task.get("progress", 0)
        checks.append((title, progress))
    return checks

def start_work(task_name, user_id):
    log = _load_work_log()
    log.append({
        "task": task_name,
        "user": str(user_id),
        "start": datetime.now(ZoneInfo("Asia/Jerusalem")).isoformat(),
        "stop": None
    })
    WORK_LOG_PATH.write_text(json.dumps(log, indent=2, ensure_ascii=False))

def stop_work(task_name, user_id):
    log = _load_work_log()
    now = datetime.now(ZoneInfo("Asia/Jerusalem")).isoformat()
    for entry in reversed(log):
        if entry.get("task") == task_name and entry.get("user") == str(user_id) and entry.get("stop") is None:
            entry["stop"] = now
            break
    WORK_LOG_PATH.write_text(json.dumps(log, indent=2, ensure_ascii=False))

def _load_work_log():
    if not WORK_LOG_PATH.exists():
        return []
    try:
        return json.loads(WORK_LOG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []

def progress_report():
    tasks = _load_db().get("tasks", {})
    total = sum(t.get("progress", 0) for t in tasks.values())
    count = len(tasks)
    overall = int(total / count) if count else 0
    lines = [f"📊 SLH PROGRESS — OVERALL {overall}%", ""]
    for task_id, task in tasks.items():
        title = task.get("title", task_id)
        progress = task.get("progress", 0)
        status = task.get("status", "active")
        lines.append(f"{title:25} {status:8} {progress}%")
    lines.append("")
    try:
        now_il = datetime.now(ZoneInfo("Asia/Jerusalem"))
    except Exception:
        now_il = datetime.now()
    lines.append(f"🕒 {now_il.strftime('%Y-%m-%d %H:%M:%S')}")
    return "\n".join(lines)
