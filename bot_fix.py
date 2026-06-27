import os
import sys
import json
import time
import telebot
import traceback
from datetime import datetime

# ---------------- CONFIG ----------------
with open("config.json") as f:
    cfg = json.load(f)

BOT_TOKEN = cfg["BOT_TOKEN"]
SUPER_ADMIN = str(cfg.get("SUPER_ADMIN"))
DB_FILE = "db.json"

bot = telebot.TeleBot(BOT_TOKEN)

# ---------------- TIME ----------------
def now():
    return datetime.now().isoformat()

# ---------------- BASE DB ----------------
BASE = {
    "users": {},
    "memory": {},
    "tasks": [],
    "agents": {},
    "events": []
}

# ---------------- LOAD / SAVE ----------------
def load():
    if not os.path.exists(DB_FILE):
        return BASE.copy()
    try:
        with open(DB_FILE) as f:
            db = json.load(f)
    except:
        db = {}

    for k in BASE:
        db.setdefault(k, BASE[k])

    return db

def save(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2)

# ---------------- SAFE USER ----------------
def ensure_user(db, uid):
    uid = str(uid)
    db["users"].setdefault(uid, {"points": 0, "created": now()})
    return db

# ---------------- EVENTS LOG ----------------
def log(db, event, data):
    db["events"].append({
        "t": now(),
        "event": event,
        "data": data
    })

    if len(db["events"]) > 500:
        db["events"] = db["events"][-500:]

# ---------------- TASK ----------------
def add_task(db, title, agent="default"):
    tid = len(db["tasks"]) + 1
    db["tasks"].append({
        "id": tid,
        "title": title,
        "agent": agent,
        "done": False,
        "t": now()
    })
    return tid

# ---------------- COMMANDS ----------------
@bot.message_handler(commands=["start"])
def start(m):
    db = ensure_user(load(), m.from_user.id)
    save(db)
    bot.reply_to(m, "🚀 SLH FIXED CORE ONLINE")

@bot.message_handler(commands=["status"])
def status(m):
    db = ensure_user(load(), m.from_user.id)
    save(db)

    bot.reply_to(m,
        f"USERS: {len(db['users'])}\n"
        f"TASKS: {len(db['tasks'])}\n"
        f"MEMORY: {len(db['memory'])}\n"
        f"EVENTS: {len(db['events'])}"
    )

@bot.message_handler(commands=["task"])
def task(m):
    db = ensure_user(load(), m.from_user.id)

    parts = m.text.split(" ", 1)
    if len(parts) < 2:
        return bot.reply_to(m, "/task <text>")

    tid = add_task(db, parts[1])
    log(db, "task.created", {"id": tid, "text": parts[1]})
    save(db)

    bot.reply_to(m, f"Task #{tid} created")

@bot.message_handler(commands=["restart"])
def restart(m):
    if str(m.from_user.id) != SUPER_ADMIN:
        return bot.reply_to(m, "Admin only")

    bot.reply_to(m, "Restarting...")
    os.execv(sys.executable, [sys.executable] + sys.argv)

# ---------------- SAFE POLLING LOOP ----------------
print("🚀 SLH FIXED CORE RUNNING")

while True:
    try:
        bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)

    except Exception as e:
        print("❌ POLLING ERROR:", repr(e))
        print(traceback.format_exc())
        time.sleep(5)
