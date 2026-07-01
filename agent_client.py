import json, os, time, subprocess, datetime

DB_PATH = "state/db.json"
AGENT_PREFIX = "mytermux"   # חייב להיות זהה לזה שמופיע ב-/agent_create

# ============================================================
# רשימה סגורה של פעולות מותרות בלבד.
# כל פעולה היא פונקציה מוגדרת מראש – אין כאן הרצת טקסט חופשי כ-shell.
# כדי להוסיף פעולה חדשה: כותבים פונקציה חדשה ומוסיפים אותה ל-ALLOWED_ACTIONS.
# ============================================================

def action_status(args):
    pid_file = os.path.expanduser("~/slh_clean/runtime/bot.pid")
    if not os.path.exists(pid_file):
        return "❌ bot.pid not found – הבוט כנראה לא רץ"
    with open(pid_file) as f:
        pid = f.read().strip()
    proc_path = f"/proc/{pid}"
    if os.path.exists(proc_path):
        return f"✅ הבוט רץ (PID {pid})"
    return f"❌ PID {pid} רשום אך אינו פעיל"

def action_restart(args):
    result = subprocess.run(
        ["bash", os.path.expanduser("~/slh_clean/start.sh")],
        capture_output=True, text=True, timeout=30
    )
    return (result.stdout + result.stderr)[:2000]

def action_logs(args):
    log_file = os.path.expanduser("~/slh_clean/logs/bot.log")
    if not os.path.exists(log_file):
        return "❌ logs/bot.log not found"
    result = subprocess.run(
        ["tail", "-n", "50", log_file],
        capture_output=True, text=True, timeout=10
    )
    return result.stdout[:3000] or "(ריק)"

def action_errors(args):
    log_file = os.path.expanduser("~/slh_clean/logs/error.log")
    if not os.path.exists(log_file):
        return "❌ logs/error.log not found"
    result = subprocess.run(
        ["tail", "-n", "50", log_file],
        capture_output=True, text=True, timeout=10
    )
    return result.stdout[:3000] or "(ריק - אין שגיאות)"

def action_sysinfo(args):
    disk = subprocess.run(["df", "-h"], capture_output=True, text=True, timeout=10).stdout
    mem = subprocess.run(["free", "-m"], capture_output=True, text=True, timeout=10).stdout
    return f"=== Disk ===\n{disk[:1000]}\n=== Memory ===\n{mem[:1000]}"

def action_uptime(args):
    result = subprocess.run(["uptime"], capture_output=True, text=True, timeout=10)
    return result.stdout.strip() or "uptime not available"

def action_whoami(args):
    result = subprocess.run(["whoami"], capture_output=True, text=True, timeout=10)
    return result.stdout.strip()

def action_dbsize(args):
    db_path = "state/db.json"
    if not os.path.exists(db_path):
        return "❌ db.json not found"
    size = os.path.getsize(db_path)
    with open(db_path) as f:
        db = json.load(f)
    students = len(db.get("students", {}))
    return f"db.json: {size} bytes, {students} students"

ALLOWED_ACTIONS = {
    "status": action_status,
    "restart": action_restart,
    "logs": action_logs,
    "errors": action_errors,
    "sysinfo": action_sysinfo,
    "uptime": action_uptime,
    "whoami": action_whoami,
    "dbsize": action_dbsize,
}


def load_db():
    with open(DB_PATH, "r") as f:
        return json.load(f)


def save_db(db):
    with open(DB_PATH, "w") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)


def process_inbox():
    db = load_db()
    agent_data = db.get("agents", {}).get(AGENT_PREFIX)
    if not agent_data:
        return
    inbox = agent_data.get("inbox", [])
    if not inbox:
        return

    outbox = agent_data.setdefault("outbox", [])

    for msg in inbox:
        action = (msg.get("command") or "").strip().lower()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if action not in ALLOWED_ACTIONS:
            outbox.append(f"[{timestamp}] ❌ '{action}' אינה פעולה מותרת. מותר: {', '.join(ALLOWED_ACTIONS)}")
            continue

        print(f"⚡ Executing allowed action: {action}")
        try:
            result = ALLOWED_ACTIONS[action](msg.get("args"))
        except subprocess.TimeoutExpired:
            result = "❌ Timeout"
        except Exception as e:
            result = f"❌ Exception: {e}"

        outbox.append(f"[{timestamp}] {action}\n>> {str(result)[:2000]}")
        print(f"📤 Result: {str(result)[:200]}")

    agent_data["inbox"] = []
    agent_data["outbox"] = outbox[-20:]
    save_db(db)


if __name__ == "__main__":
    print(f"🔁 Agent client running (allowlist-only: {', '.join(ALLOWED_ACTIONS)})")
    print("ממתין לפקודות ב-db.json -> agents.mytermux.inbox ...")
    while True:
        try:
            process_inbox()
        except Exception as e:
            print(f"⚠️ Loop error: {e}")
        time.sleep(2)
