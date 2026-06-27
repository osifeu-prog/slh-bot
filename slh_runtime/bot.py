import telebot
import json
import os
from datetime import datetime

TOKEN = "PUT_YOUR_TOKEN_HERE"
bot = telebot.TeleBot(TOKEN)

DB_PATH = "db.json"

# ---------------- DB ----------------
def load():
    if not os.path.exists(DB_PATH):
        return {
            "users": {},
            "agents": {},
            "tasks": {},
            "votes": {},
            "wallets": {}
        }
    return json.load(open(DB_PATH))

def save(db):
    json.dump(db, open(DB_PATH, "w"), indent=2)

def now():
    return datetime.now().isoformat()

# ---------------- INIT ----------------
def get_db():
    return load()

# ---------------- USERS ----------------
def ensure_user(db, uid):
    uid = str(uid)
    if uid not in db["users"]:
        db["users"][uid] = {"points": 0, "created": now()}
        db["wallets"][uid] = {"balance": 0}
    return db

# ---------------- AGENTS ----------------
def create_agent(db, name, owner):
    aid = str(len(db["agents"]) + 1)
    db["agents"][aid] = {
        "name": name,
        "owner": str(owner),
        "tasks": [],
        "status": "idle",
        "created": now()
    }
    return aid

# ---------------- TASKS ----------------
def create_task(db, title, agent_id, creator):
    tid = str(len(db["tasks"]) + 1)
    db["tasks"][tid] = {
        "title": title,
        "agent": agent_id,
        "creator": str(creator),
        "done": False,
        "created": now()
    }
    db["agents"][agent_id]["tasks"].append(tid)
    return tid

# ---------------- VOTES ----------------
def vote(db, uid, key):
    uid = str(uid)
    db["votes"].setdefault(key, {"count": 0, "voters": []})

    if uid in db["votes"][key]["voters"]:
        return False

    db["votes"][key]["count"] += 1
    db["votes"][key]["voters"].append(uid)

    db["users"][uid]["points"] += 1
    db["wallets"][uid]["balance"] += 1
    return True

# ---------------- COMMANDS ----------------
@bot.message_handler(commands=["start"])
def start(m):
    db = get_db()
    db = ensure_user(db, m.from_user.id)
    save(db)
    bot.reply_to(m, "SLH SYSTEM ONLINE\n/agent /task /vote /wallet /status")

@bot.message_handler(commands=["status"])
def status(m):
    db = get_db()
    db = ensure_user(db, m.from_user.id)
    save(db)

    bot.reply_to(m,
        f"USERS: {len(db['users'])}\n"
        f"AGENTS: {len(db['agents'])}\n"
        f"TASKS: {len(db['tasks'])}"
    )

# -------- AGENTS --------
@bot.message_handler(commands=["agent"])
def agent(m):
    db = get_db()
    db = ensure_user(db, m.from_user.id)

    parts = m.text.split(" ", 2)

    if len(parts) < 2:
        bot.reply_to(m, "Usage:\n/agent create <name>\n/agent list")
        return

    cmd = parts[1]

    if cmd == "create":
        name = parts[2] if len(parts) > 2 else "agent"
        aid = create_agent(db, name, m.from_user.id)
        save(db)
        bot.reply_to(m, f"Agent created: {aid} ({name})")

    elif cmd == "list":
        txt = "\n".join([f"{k}: {v['name']} ({v['status']})" for k,v in db["agents"].items()])
        bot.reply_to(m, txt if txt else "No agents")

# -------- TASKS --------
@bot.message_handler(commands=["task"])
def task(m):
    db = get_db()
    db = ensure_user(db, m.from_user.id)

    parts = m.text.split(" ", 3)

    if len(parts) < 2:
        bot.reply_to(m, "Usage:\n/task create <agent_id> <title>")
        return

    cmd = parts[1]

    if cmd == "create":
        if len(parts) < 4:
            bot.reply_to(m, "Usage: /task create <agent_id> <title>")
            return

        agent_id = parts[2]
        title = parts[3]

        if agent_id not in db["agents"]:
            bot.reply_to(m, "Agent not found")
            return

        tid = create_task(db, title, agent_id, m.from_user.id)
        save(db)
        bot.reply_to(m, f"Task created: {tid}")

    elif cmd == "list":
        txt = "\n".join([f"{k}: {v['title']} (agent {v['agent']})" for k,v in db["tasks"].items()])
        bot.reply_to(m, txt if txt else "No tasks")

# -------- VOTE + ECONOMY --------
@bot.message_handler(commands=["vote"])
def vote_cmd(m):
    db = get_db()
    db = ensure_user(db, m.from_user.id)

    parts = m.text.split(" ", 1)
    if len(parts) < 2:
        bot.reply_to(m, "Usage: /vote yes|no|unsure")
        return

    key = parts[1].strip()

    if vote(db, m.from_user.id, key):
        save(db)
        bot.reply_to(m, f"Voted: {key} (+1 point)")
    else:
        bot.reply_to(m, "Already voted")

# -------- WALLET --------
@bot.message_handler(commands=["wallet"])
def wallet(m):
    db = get_db()
    db = ensure_user(db, m.from_user.id)
    save(db)

    bal = db["wallets"][str(m.from_user.id)]["balance"]
    pts = db["users"][str(m.from_user.id)]["points"]

    bot.reply_to(m, f"Wallet: {bal}\nPoints: {pts}")

# ---------------- RUN ----------------
print("SLH SYSTEM RUNNING")
bot.infinity_polling()
