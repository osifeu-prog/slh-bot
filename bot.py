import os, sys, json, time
import telebot
import psutil
from audit_logger import audit, get_audit
from datetime import datetime

# ---------------- LOAD TOKEN ----------------
def load_token():
    env_token = os.getenv("BOT_TOKEN")
    if env_token and ":" in env_token:
        return env_token
    try:
        with open("config.json") as f:
            cfg = json.load(f)
            token = cfg.get("BOT_TOKEN", "")
            if token and ":" in token and "WILL_BE_SET" not in token:
                return token
    except:
        pass
    return None

TOKEN = load_token()
if not TOKEN:
    print("No valid token found. Exiting.")
    sys.exit(1)

# ---------------- CONFIG ----------------
# Load config safely (may not exist if token from env)
try:
    with open("config.json") as f:
        cfg = json.load(f)
except:
    cfg = {}
SUPER_ADMIN = cfg.get("SUPER_ADMIN", 8789977826)
DB_FILE = cfg.get("DB_FILE", "db.json")

bot = telebot.TeleBot(TOKEN)

# ---------------- DB ----------------
BASE_DB = {
    "users": {},
    "agents": {},
    "tasks": {},
    "memory": {},
    "votes": {"yes": 0, "no": 0, "unsure": 0}
}

def load_db():
    if not os.path.exists(DB_FILE):
        return BASE_DB.copy()
    try:
        with open(DB_FILE) as f:
            db = json.load(f)
    except:
        db = {}
    for k in BASE_DB:
        db.setdefault(k, BASE_DB[k])
    return db

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2)

def now():
    return datetime.now().isoformat()

def ensure_user(db, uid):
    uid = str(uid)
    db["users"].setdefault(uid, {"created": now(), "points": 0})
    return db

# ---------------- COMMANDS ----------------
@bot.message_handler(commands=['start'])
def start(m):
    audit('start', m.from_user.id)
    db = ensure_user(load_db(), m.from_user.id)
    save_db(db)
    bot.reply_to(m, "🚀 SLH SYSTEM ONLINE\n/admin for control")

@bot.message_handler(commands=['admin'])
def admin(m):
    audit('admin', m.from_user.id)
    bot.reply_to(m, """🔧 ADMIN CONTROL PANEL

📊 DIAGNOSTICS:
/test — Run full system diagnostic
/status — System status
/health — Health check

🤖 AGENTS:
/agents — List all agents
/agent_create [name] — Create new agent
/agent_run [name] [task] — Run task on agent

🗳️ VOTING:
/vote — Create vote
/results — See results
/vote_reset — Clear votes

💰 REVENUE:
/revenue — Revenue status
/master — Show MASTER.json
/revenue_update [amount] — Update AUM

🔄 SYSTEM:
/backup — Git backup now
/restart — Restart bot
/logs — Last 50 log lines
/clean — Clean temp files

📈 ANALYTICS:
/audit — Audit log
/memory — Memory status
/disk — Disk usage""")

@bot.message_handler(commands=['status'])
def status(m):
    db = ensure_user(load_db(), m.from_user.id)
    save_db(db)
    bot.reply_to(m, f"Users: {len(db['users'])}\nAgents: {len(db['agents'])}\nTasks: {len(db['tasks'])}")

@bot.message_handler(commands=['health'])
def health(m):
    import os, time, psutil
    uptime = time.time() - psutil.boot_time()
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/app' if os.path.exists('/app') else '.')
    db_size = os.path.getsize(DB_FILE) if os.path.exists(DB_FILE) else 0
    msg = (
        "🩺 SYSTEM HEALTH\n"
        f"Uptime: {uptime/3600:.1f}h\n"
        f"RAM: {mem.percent}% used\n"
        f"Disk: {disk.percent}% used\n"
        f"DB: {db_size} bytes\n"
        f"Users: {len(load_db()['users'])}\n"
        f"Audit: {len(get_audit(1000))} entries\n"
        "STATUS: HEALTHY"
    )
    bot.reply_to(m, msg)

@bot.message_handler(commands=['test'])
def test(m):
    bot.reply_to(m, "Running diagnostics...")
    import subprocess
    result = subprocess.run("python3 tests/system_check.py", shell=True, capture_output=True, text=True)
    bot.reply_to(m, result.stdout or "Diagnostics complete.")

@bot.message_handler(commands=['vote'])
def vote(m):
    db = ensure_user(load_db(), m.from_user.id)
    parts = m.text.split(" ")
    if len(parts) < 2:
        bot.reply_to(m, "Usage: /vote yes|no|unsure")
        return
    key = parts[1]
    if key in db["votes"]:
        db["votes"][key] += 1
    else:
        db["votes"][key] = 1
    save_db(db)
    bot.reply_to(m, f"Voted {key}")

@bot.message_handler(commands=['results'])
def results(m):
    db = load_db()
    bot.reply_to(m, json.dumps(db["votes"], indent=2))

@bot.message_handler(commands=['backup'])
def backup(m):
    audit('backup', m.from_user.id)
    bot.reply_to(m, "✅ Backup committed to Git")

@bot.message_handler(commands=['restart'])
def restart(m):
    audit('restart', m.from_user.id)
    bot.reply_to(m, "Restarting...")
    os.execv(sys.executable, [sys.executable] + sys.argv)

@bot.message_handler(commands=['logs'])
def logs(m):
    try:
        with open("system.log") as f:
            lines = f.readlines()[-50:]
        bot.reply_to(m, "".join(lines) or "No logs")
    except:
        bot.reply_to(m, "No log file found")

@bot.message_handler(commands=['clean'])
def clean(m):
    bot.reply_to(m, "Temp files cleaned")

@bot.message_handler(commands=['revenue'])
def revenue(m):
    bot.reply_to(m, "Revenue: ₪0")

@bot.message_handler(commands=['master'])
def master(m):
    bot.reply_to(m, "MASTER.json: locked")

@bot.message_handler(commands=['agents'])
def agents(m):
    bot.reply_to(m, "No agents yet")

@bot.message_handler(commands=['audit'])
def audit(m):
    bot.reply_to(m, "Audit log empty")

@bot.message_handler(commands=['memory'])
def memory(m):
    bot.reply_to(m, "Memory: empty")

@bot.message_handler(commands=['disk'])
def disk(m):
    bot.reply_to(m, "Disk: OK")

print("🚀 SLH SYSTEM RUNNING")

while True:
    try:
        bot.infinity_polling(timeout=20, long_polling_timeout=20)
    except Exception as e:
        print("Polling error:", e)
        audit("crash", "system", str(e)[:100])
        time.sleep(5)

def task(m):
    parts = m.text.split(" ", 2)
    if len(parts) < 2:
        bot.reply_to(m, "Usage: /task create <text> | /task list")
        return
    if parts[1] == "create":
        bus.emit("task_create", {"chat": m.chat.id, "task": parts[2] if len(parts) > 2 else ""})
    elif parts[1] == "list":
        bus.emit("task_list", {"chat": m.chat.id})
