import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

DB_PATH = Path("state/db.json")
WORK_LOG_PATH = Path("state/work_log.json")

TASK_CATEGORY_MAP = {
    "alpha_identity": "Identity",
    "alpha_wallet": "Wallet",
    "alpha_agents": "AI Agents",
    "alpha_academy": "Academy",
    "alpha_economy": "Economy authority",
    "alpha_store": "Store",
    "alpha_user_journey": "Real user journey",
    "alpha_exchange": "Exchange (Binance)",
}

def _load_db():
    return json.loads(DB_PATH.read_text(encoding="utf-8"))

def get_progress():
    db = _load_db()
    tasks = db.get("tasks", {})
    services = db.get("system_services", {})
    users = db.get("users", {})
    ledger = db.get("ledger", [])
    agents = db.get("agents", {})

    checks = []

    # Infrastructure / Runtime / Security are foundation
    checks.append(("Infrastructure", 90 if DB_PATH.exists() else 0))
    checks.append(("Runtime", 90 if Path("bot_gateway.py").exists() else 0))
    checks.append(("Security", 85 if Path("handlers/firewall_handler.py").exists() else 0))

    # Category progress from tasks
    for task_id, label in TASK_CATEGORY_MAP.items():
        task = tasks.get(task_id, {})
        progress = task.get("progress", 0)
        checks.append((label, progress))

    # Ledger integrity
    checks.append(("Ledger Integrity", 100 if ledger else 0))

    # sort to keep stable order
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
        "start": datetime.now(ZoneInfo("Asia/Jerusalem")).isoformat(),
        "stop": None
    })
    WORK_LOG_PATH.write_text(json.dumps(log, indent=2, ensure_ascii=False))
    return True

def stop_work(task_name, user_id):
    log = _load_work_log()
    now = datetime.now(ZoneInfo("Asia/Jerusalem")).isoformat()
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
    try:
        now_il = datetime.now(ZoneInfo("Asia/Jerusalem"))
    except Exception:
        now_il = datetime.now()
    lines.append(f"🕒 {now_il.strftime('%Y-%m-%d %H:%M:%S')}")
    return "\n".join(lines)
