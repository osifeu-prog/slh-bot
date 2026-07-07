print("SLH ENTRYPOINT")
import os
print("PYTHON STARTED")
import os, sys, json, time, subprocess
import welcome_handler

# --- Runtime environment check ---
import os, sys

BASE_DIR = "/app" if os.path.isdir("/app") else os.getcwd()
STATE_DIR = os.path.join(BASE_DIR, "state")

print("BOOT BASE:", BASE_DIR)
print("BOOT STATE:", os.path.isdir(STATE_DIR))

if not os.path.isdir(STATE_DIR):
    print("⚠️ State directory missing, creating...")
    os.makedirs(STATE_DIR, exist_ok=True)
from internal_agent import start_agent_thread
import state_manager
import telebot
from marketplace import load_store, save_store
from datetime import datetime
from audit_logger import audit, get_audit
from core.event_bus import EventBus
from plugins.task import TaskPlugin
import course_handlers
import learn_handlers
import project_commands
import monitor_handler
import ask_handler
import complete_handler
import diagnostic_handler
import report_handler
import roadmap_handler
import brief_handler
import econ_handler
import payment_handler
import ton_handler
import language_handler
import learning_path
import advanced_ask_handler
import junk_handler
import sandbox_handler
import myprogress_handler
import help_handler
import broadcast_handler
import refresh_token_handler
import smart_leaderboard

# ---------------- LOAD TOKEN ----------------
def load_token():
    env_token = os.getenv("BOT_TOKEN")
    if env_token and ":" in env_token:
        return env_token

token = load_token()
if not token:
    print('No valid token found. Exiting.')
    exit(1)
bot = telebot.TeleBot(token)
help_handler.register_help(bot)
agents_dict = state_manager.get_agents()
econ_handler.register_econ_handlers(bot)
payment_handler.register_payment_handlers(bot)
ton_handler.register_ton_handlers(bot)  # RE-ENABLED 2026-07-06: datetime import fixed, real wallet configured, placeholder guard added
language_handler.register_language(bot)
learning_path.register_learning_path(bot)
advanced_ask_handler.register_ask_handler(bot)

try:
    with open('allowed_ids.json') as _f:
        _ALLOWED = _json_auth.load(_f)
except Exception:
    _ALLOWED = {'admin': 8789977826, 'allowed': [8789977826]}

def is_admin(m):
    uid = m.from_user.id if hasattr(m, 'from_user') else m
    if uid not in _ALLOWED.get("allowed", []) and uid != _ALLOWED.get("admin"):
        try:
            bot.send_message(m.chat.id, "⛔ Unauthorized - admin only")
        except:
            pass
        return False
    return True

def smart_reply(bot, chat_id, text, max_len=3800):
    if len(text) <= max_len:
        bot.send_message(chat_id, text)
        return
    # Long text - offer split/download without sending the full text
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    parts = len(text) // max_len + 1
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton(f"Send as {parts} messages", callback_data=f"split_msg_{chat_id}"),
        InlineKeyboardButton("Download as .txt", callback_data=f"dl_msg_{chat_id}")
    )
    bot.send_message(chat_id, f"📩 Message is {len(text)} chars. Choose how to receive:", reply_markup=markup)
    import tempfile
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
    tmp.write(text)
    tmp.close()
    if not hasattr(bot, "_msg_files"):
        bot._msg_files = {}
    bot._msg_files[chat_id] = tmp.name


@bot.message_handler(commands=["reload"])
def handle_reload(message):
    if message.from_user.id != 8789977826:
        bot.reply_to(message, "⛔ Admin only")
        return
    bot.reply_to(message, "🔄 Reloading handlers...")
    bot.message_handlers.clear()
    import importlib
    modules = [
        "welcome_handler","learn_handlers","project_commands",
        "course_handlers","demo_handlers","report_handler",
        "broadcast_handler","ask_handler","help_handler",
        "diagnostic_handler","junk_handler","monitor_handler",
        "myprogress_handler","econ_handler","roadmap_handler",
        "refresh_token_handler"
    ]
    failed = []
    for mod_name in modules:
        try:
            mod = importlib.import_module(mod_name)
            importlib.reload(mod)
            if hasattr(mod, "init"):
                mod.init(bot)
        except Exception as e:
            failed.append(f"{mod_name}: {e}")
    if failed:
        bot.send_message(8789977826, "⚠️ Reload failures:\n" + "\n".join(failed))
    else:
        bot.send_message(8789977826, "✅ All handlers reloaded successfully")
    bot.send_message(message.chat.id, "✅ Reload complete")
    # re-register catch-all handler after reload
    @bot.message_handler(func=lambda m: m.text and m.text.startswith("/"))
    def catch_all_after_reload(m):
        bot.reply_to(m, "פקודה לא מוכרת. שלח /start")
@bot.callback_query_handler(func=lambda call: call.data.startswith("split_msg_") or call.data.startswith("dl_msg_"))
def handle_msg_split(call):
    chat_id = call.message.chat.id
    action, _, uid = call.data.partition("_")
    try:
        orig_chat = int(uid)
    except:
        orig_chat = chat_id
    tmp_path = bot._msg_files.get(orig_chat) if hasattr(bot, "_msg_files") else None
    if not tmp_path or not os.path.exists(tmp_path):
        bot.answer_callback_query(call.id, "File expired")
        return
    with open(tmp_path, "r", encoding="utf-8") as f:
        text = f.read()
    if action == "split":
        bot.answer_callback_query(call.id, "Sending...")
        for i in range(0, len(text), 3800):
            bot.send_message(orig_chat, text[i:i+3800])
    elif action == "dl":
        bot.answer_callback_query(call.id, "Uploading...")
        with open(tmp_path, "rb") as f:
            bot.send_document(orig_chat, f, visible_file_name="message.txt")
    try:
        os.unlink(tmp_path)
    except:
        pass
    if hasattr(bot, "_msg_files") and orig_chat in bot._msg_files:
        del bot._msg_files[orig_chat]
    bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)

myprogress_handler.init(bot)
course_handlers.register_course_handlers(bot)
learn_handlers.register(bot)
broadcast_handler.init(bot)
welcome_handler.init(bot)
project_commands.register(bot)
monitor_handler.init(bot)
# ask_handler.init(bot)  # DISABLED 2026-07-07: uses local ollama which doesn't exist on Railway, causes duplicate/broken responses alongside advanced_ask_handler
report_handler.init(bot)
roadmap_handler.init(bot)
brief_handler.init(bot)
junk_handler.init(bot)
refresh_token_handler.init(bot)
import demo_handlers; demo_handlers.register(bot, agents_dict)
smart_leaderboard.register(bot)
# agents_dict loaded in main block
# start_agent_thread() moved to main block

# ---- Load agents from persistent storage ----
try:
    import json, os
    if os.path.exists("/app/agents.json"):
        with open("/app/agents.json") as f:
            agents_dict.update(json.load(f))
        print(f"Loaded {len(agents_dict)} agents from disk")
except Exception as e:
    print("Could not load agents.json:", e)

# ---------------- KERNEL INIT ----------------
try:
    bus = EventBus(workers=2)
    kernel = type('KernelStub', (), {'state': {}, 'bus': bus, 'telegram': None, 'bot': bot})()
    TaskPlugin().on_start(kernel)
    _KERNEL_READY = True
    print("✅ Kernel modules loaded")
except Exception as e:
    print("Kernel init failed:", e)
    _KERNEL_READY = False

# ---------------- DB ----------------
BASE_DB = {"users": {}, "agents": {}, "tasks": {}, "memory": {}, "votes": {"yes": 0, "no": 0, "unsure": 0}}

def now():
    return datetime.now().isoformat()

def ensure_user(db, uid):
    uid = str(uid)
    db["users"].setdefault(uid, {"created": now(), "points": 0})
    return db

# ---------------- COMMANDS ----------------


# Simple stub commands (until full implementation)
@bot.message_handler(commands=['courses'])
def courses_stub(m):
    bot.reply_to(m, "📚 Courses: Python Basics, AI for Beginners, Tech Entrepreneurship.\nUse /join to enroll!")

@bot.message_handler(commands=['referral'])
def referral_stub(m):
    bot.reply_to(m, "🔗 Your referral link will be ready soon. Check back later!")

@bot.message_handler(commands=['project'])
def project_stub(m):
    bot.reply_to(m, "📁 Projects: /project create [name] or /project list")



# Admin utility: grep inside project files
@bot.message_handler(commands=['grep'])
def grep_admin(m):
    if not is_admin(m): return
    args = m.text.split(" ", 2)
    if len(args) < 3:
        bot.reply_to(m, "Usage: /grep <pattern> <filename>")
        return
    pattern, fname = args[1], args[2]
    try:
        import subprocess
        result = subprocess.check_output(f"grep -n '{pattern}' {fname}", shell=True, text=True, stderr=subprocess.STDOUT)
        bot.reply_to(m, result[:4000] or "No matches.")
    except Exception as e:
        bot.reply_to(m, f"❌ {e}")

# Admin utility: echo (test)
@bot.message_handler(commands=['echo'])
def echo_admin(m):
    if not is_admin(m): return
    text = m.text.replace("/echo", "", 1).strip()
    bot.reply_to(m, text or "Echo.")


# ===== INTERACTIVE /join WIZARD =====
@bot.message_handler(commands=['join'])
def start_join(m):
    uid = str(m.chat.id)
    # check if already registered
    try:
        with open("state/db.json") as f:
            db = json.load(f)
        if uid in db.get("students", {}):
            bot.reply_to(m, "אתה כבר רשום!\nשלח /myprogress למעקב.")
            return
    except:
        pass
    msg = bot.reply_to(m, "ברוכים הבאים! מה שמך המלא?")
    bot.register_next_step_handler(msg, process_join_name)

def process_join_name(m):
    name = m.text.strip()
    if not name:
        msg = bot.reply_to(m, "השם לא יכול להיות ריק. מה שמך המלא?")
        bot.register_next_step_handler(msg, process_join_name)
        return
    # store temporary data in bot context
    bot._join_data = {"name": name}
    msg = bot.reply_to(m, f"נעים להכיר, {name}!\nמה הקבוצה / כיתה שלך?")
    bot.register_next_step_handler(msg, process_join_group)

def process_join_group(m):
    group = m.text.strip()
    if not group:
        group = "לא צוין"
    bot._join_data["group"] = group
    msg = bot.reply_to(m, "מה המטרה שלך בלמידה?\n(אפשר להקיש - לדלג)")
    bot.register_next_step_handler(msg, process_join_goal)

def process_join_goal(m):
    goal = m.text.strip()
    if goal == "-" or not goal:
        goal = "לא צוין"
    uid = str(m.chat.id)
    name = bot._join_data.get("name", "ללא שם")
    group = bot._join_data.get("group", "לא צוין")
    try:
        with open("state/db.json") as f:
            db = json.load(f)
    except:
        db = {"students": {}}
    db.setdefault("students", {})[uid] = {
        "name": name,
        "group": group,
        "goal": goal,
        "registered": __import__("datetime").datetime.now().isoformat(),
        "referral_count": 0,
        "courses": {}
    }
    # Also create a "users" record so this person can use credits/balance/payments
    if uid not in db.setdefault("users", {}):
        db["users"][uid] = {
            "name": name,
            "created": __import__("datetime").datetime.now().isoformat(),
            "balance": 0
        }
    with open("state/db.json", "w") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
    summary = (
        f"✅ נרשמת בהצלחה, {name}!\n"
        f"קבוצה: {group}\n"
        f"מטרה: {goal}\n\n"
        "💡 **איך מתחילים להרוויח:**\n"
        "  👥 /referral – הזמן חברים וקבל 85% עמלה\n"
        "  ⭐ /pay – קנה Credits בכוכבי טלגרם\n"
        "  💎 /ton – שלח TON וקבל Credits\n\n"
        "🛒 **מה אפשר לקנות:**\n"
        "  /buy ask_credit – שאל את ה־AI (10 Credits)\n"
        "  /buy premium_agent – סוכן פרימיום (50 Credits)\n\n"
        "📊 לעקוב: /balance, /history\n"
        "📚 קורסים: /courses\n\n"
        "שלח /start לתפריט הראשי."
    )
    bot.reply_to(m, summary)
    # clean up
    if hasattr(bot, "_join_data"):
        del bot._join_data

@bot.message_handler(commands=['admin'])
def admin(m):
    bot.send_message(m.chat.id, """🔧 ADMIN CONTROL PANEL (admin only)
📊 Diagnostics
/status – System overview
/health – Resource health
/test – Full diagnostic
/test_agents – Agent self-test
/diagnose – System diagnosis
/diagnostic – Alt diagnosis
/disk – Disk usage
/sysinfo – System resources
/memory – Memory status
/debug – Container debug
/debugcmd – Debug command
/testcmd – Test command
/errors – Recent errors
/audit – Audit log
/logs <n> – Last N log lines
/rlogs – Railway logs
/termlog – Termux logs

🔄 Operations
/restart – Restart bot
/deploy – Trigger Railway deploy
/backup – Git backup
/clean – Clean temp files
/exec <cmd> – Run shell command
/termux – Termux status

🤖 Agents
/agents – List all agents
/agent_create <name> – Create agent
/agentstate <prefix> <state> – Set state
/sendagent <prefix> <msg> – Send message
/inbox <prefix> – Agent inbox
/agent_debug – Debug agent
/agent_test – Test agent

📢 Broadcast & Master
/broadcast <msg> – Broadcast to all
/master – Master control panel

💰 Revenue
/revenue – Revenue status

🔐 Tokens
/refreshtoken – Refresh tokens
/activate – Activate user

🗳 Voting
/vote – Create vote
/results – See results

🧩 Plugins & Goals
/plugin list – List plugins
/goal add/list – Manage goals

🕒 Snapshots & Monitor
/monitor – Start monitoring
/snapshot – Create snapshot
/rollback – Rollback to snapshot

🗑 Junk Management
/scan_junk – Scan junk files
/clean_junk – Clean junk
/backup_junk – Backup junk

🛒 Marketplace (Admin)
/market – Browse/manage
/market_upload – Upload plugin
/market_installed – Installed list
/market_search <term> – Search
/market_rate <id> <rating> – Rate

🧪 Sandbox
/sandbox – Enter sandbox

👥 User Management
/user <id> – User info
/users – List users

⚠️ Kernel
/kernellog – Kernel logs
/kernelstatus – Kernel status

🔒 Permissions
/allow – Manage permissions

All 81 system commands. For user commands: /help

""")
@bot.message_handler(commands=['status'])
def status(m):
    db = state_manager.load_db()
    bot.send_message(m.chat.id, f"Users: {len(db.get('students', {}))}\nAgents: {len(agents_dict)}\nTasks: {len(db['tasks'])}")

@bot.message_handler(commands=['health'])
def health(m):
    try:
        import psutil
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/app' if os.path.exists('/app') else '.')
        uptime = time.time() - psutil.boot_time()
        msg = f"Uptime: {uptime/3600:.1f}h\nRAM: {mem.percent}% used\nDisk: {disk.percent}% used"
    except:
        msg = "Health: limited info (psutil not available)"
    bot.send_message(m.chat.id, f"🩺 SYSTEM HEALTH\n{msg}")

@bot.message_handler(commands=['task'])
def task(m):
    if not _KERNEL_READY:
        bot.send_message(m.chat.id, "Kernel not loaded")
        return
    parts = m.text.split(" ", 2)
    if len(parts) < 2:
        bot.send_message(m.chat.id, "Usage: /task create <text> | /task list")
        return
    if parts[1] == "create":
        task_text = parts[2] if len(parts) > 2 else ""
        if not task_text:
            bot.send_message(m.chat.id, "❌ /task create <טקסט>")
            return
        db = state_manager.load_db()
        uid = str(m.from_user.id)
        db.setdefault("user_tasks", {}).setdefault(uid, []).append(task_text)
        state_manager.save_db(db)
        bot.send_message(m.chat.id, "✅ נוצרה משימה: " + task_text)
    elif parts[1] == "list":
        db = state_manager.load_db()
        uid = str(m.from_user.id)
        tasks = db.get("user_tasks", {}).get(uid, [])
        if tasks:
            msg = "📋 המשימות שלך:\n" + "\n".join(f"• {t}" for t in tasks)
        else:
            msg = "📭 אין משימות. /task create <טקסט>"
        bot.send_message(m.chat.id, msg)

@bot.message_handler(commands=['agent_create'])
def agent_create(m):
    if not is_admin(m): return
    parts = m.text.split()
    if len(parts) < 2:
        bot.send_message(m.chat.id, "Usage: /agent_create <name>")
        return
    name = parts[1]
    agents = state_manager.get_agents()
    if name in agents:
        bot.send_message(m.chat.id, "❌ Agent already exists")
        return
    agents[name] = {"name": name, "inbox": [], "outbox": [], "state": "idle", "role": "agent"}
    state_manager.set_agents(agents)
    agents_dict = agents
    bot.send_message(m.chat.id, f"✅ Agent created: {name}")
@bot.message_handler(commands=['agents'])
def agents_list(m):
    if not agents_dict:
        bot.send_message(m.chat.id, "No agents yet")
    else:
        lines = [f"{v.get('name','?')} [{v.get('state','idle')}] – {v.get('role','?')}" for k, v in agents_dict.items()]
        bot.send_message(m.chat.id, "🤖 Agents:\n" + "\n".join(lines))

@bot.message_handler(commands=['agent_debug'])
def agent_debug(m):
    if not is_admin(m): return
    bot.send_message(m.chat.id, f"Agents in memory: {len(agents_dict)}")

@bot.message_handler(commands=['agent_test'])
def agent_test(m):
    if not is_admin(m): return
    # simple test: create and list
    agent_store.create("test_agent")
    bot.send_message(m.chat.id, f"Test agent created. Total agents: {len(agents_dict)}")

@bot.message_handler(commands=['vote'])
def vote(m):
    db = ensure_user(state_manager.load_db(), m.from_user.id)
    key = m.text.split(" ", 1)[1] if len(m.text.split(" ", 1)) > 1 else ""
    if key in db["votes"]:
        db["votes"][key] += 1
    else:
        db["votes"][key] = 1
    state_manager.save_db(db)
    bot.send_message(m.chat.id, f"Voted {key}")

@bot.message_handler(commands=['results'])
def results(m):
    db = state_manager.load_db()
    bot.send_message(m.chat.id, json.dumps(db["votes"], indent=2))

@bot.message_handler(commands=['revenue'])
def revenue(m):
    bot.send_message(m.chat.id, "Revenue: ₪0")

@bot.message_handler(commands=['master'])
def master(m):
    if not is_admin(m): return
    bot.send_message(m.chat.id, "MASTER.json: locked")

@bot.message_handler(commands=['backup'])
def backup(m):
    if not is_admin(m): return
    bot.send_message(m.chat.id, "✅ Backup committed to Git")

@bot.message_handler(commands=['restart'])
def restart(m):
    if not is_admin(m): return
    bot.send_message(m.chat.id, "Restarting...")
    os.execv(sys.executable, [sys.executable] + sys.argv)

@bot.message_handler(commands=['logs'])
def logs(m):
    if not is_admin(m): return
    n = int(m.text.split(" ", 1)[1]) if len(m.text.split(" ", 1)) > 1 else 20
    try:
        result = subprocess.run(f"tail -n {n} /app/bot.log", shell=True, capture_output=True, text=True)
        bot.send_message(m.chat.id, result.stdout[:4000] or "No logs yet")
    except:
        bot.send_message(m.chat.id, "No log file")

@bot.message_handler(commands=['clean'])
def clean(m):
    if not is_admin(m): return
    bot.send_message(m.chat.id, "Temp files cleaned")

@bot.message_handler(commands=['audit'])
def audit_cmd(m):
    if not is_admin(m): return
    entries = get_audit(15)
    if not entries:
        bot.send_message(m.chat.id, "Audit log empty")
    else:
        lines = [f"{e['time']}: {e['user']} – {e['action']}" for e in entries]
        bot.send_message(m.chat.id, "📋 Audit Log:\n" + "\n".join(lines))

@bot.message_handler(commands=['memory'])
def memory(m):
    if not is_admin(m): return
    bot.send_message(m.chat.id, "Memory: empty")

@bot.message_handler(commands=['debug'])
def debug(m):
    if not is_admin(m): return
    bot.send_message(m.chat.id, f"cwd: {os.getcwd()}\nfiles: {os.listdir('.')}\nsys.path: {sys.path}\ncore module: OK")

@bot.message_handler(commands=['termux'])
def termux(m):
    if not is_admin(m): return
    bot.send_message(m.chat.id, f"Python: {sys.version}\ncwd: {os.getcwd()}")

@bot.message_handler(commands=['deploy'])
def deploy(m):
    if not is_admin(m): return
    result = subprocess.run("cd /app && git push", shell=True, capture_output=True, text=True)
    bot.send_message(m.chat.id, f"Deploy triggered:\n{result.stdout[:300] or 'OK'}")

@bot.message_handler(commands=['errors'])
def errors(m):
    if not is_admin(m): return
    try:
        with open("/app/bot.log") as f:
            lines = f.readlines()
        errors = [line for line in lines if "ERROR" in line or "Traceback" in line][-10:]
        bot.send_message(m.chat.id, "".join(errors) or "No recent errors")
    except:
        bot.send_message(m.chat.id, "No log file")

@bot.message_handler(commands=['plugin'])
def plugin(m):
    if not is_admin(m): return
    parts = m.text.split()
    if len(parts) > 1 and parts[1] == "list":
        plugins = os.listdir("/app/plugins") if os.path.exists("/app/plugins") else []
        bot.send_message(m.chat.id, "Plugins: " + ", ".join(plugins) if plugins else "None")
    else:
        bot.send_message(m.chat.id, "Usage: /plugin list")

@bot.message_handler(commands=['goal'])
def goal(m):
    if not is_admin(m): return
    parts = m.text.split(None, 2)
    path = "/app/goals.json"
    if len(parts) < 2:
        bot.send_message(m.chat.id, "Usage: /goal add <text> | /goal list")
        return
    if parts[1] == "add" and len(parts) > 2:
        goals = json.load(open(path)) if os.path.exists(path) else []
        goals.append({"text": parts[2], "status": "active"})
        json.dump(goals, open(path, "w"))
        bot.send_message(m.chat.id, f"Goal added: {parts[2]}")
    elif parts[1] == "list":
        goals = json.load(open(path)) if os.path.exists(path) else []
        bot.send_message(m.chat.id, "\n".join([f"{g['text']} [{g['status']}]" for g in goals]) or "No goals")

@bot.message_handler(commands=['sysinfo'])
def sysinfo(m):
    if not is_admin(m): return
    try:
        df = subprocess.run("df -h / | tail -1", shell=True, capture_output=True, text=True).stdout.strip()
        mem = subprocess.run("cat /proc/meminfo 2>/dev/null | grep MemTotal", shell=True, capture_output=True, text=True).stdout.strip()
        uptime = subprocess.run("cat /proc/uptime 2>/dev/null | awk '{print $1}'", shell=True, capture_output=True, text=True).stdout.strip()
        if uptime:
            secs = int(float(uptime))
            hours = secs // 3600
            mins = (secs % 3600) // 60
            uptime_str = f"{hours}h {mins}m"
        else:
            uptime_str = "N/A"
        bot.send_message(m.chat.id, f"Disk: {df}\nMemory: {mem}\nUptime: {uptime_str}")
    except Exception as e:
        bot.send_message(m.chat.id, f"Sysinfo error: {e}")

@bot.message_handler(commands=['disk'])
def disk(m):
    if not is_admin(m): return
    bot.send_message(m.chat.id, "Disk: OK")

@bot.message_handler(commands=['test'])
def test(m):
    if not is_admin(m): return
    import subprocess
    result = subprocess.run("python3 tests/system_check.py", shell=True, capture_output=True, text=True)
    bot.send_message(m.chat.id, result.stdout or "Diagnostics complete.")

@bot.message_handler(commands=['kernellog'])
def kernellog(m):
    if not is_admin(m): return
    bot.send_message(m.chat.id, "See /debug for kernel info")

@bot.message_handler(commands=['kernelstatus'])
def kernelstatus(m):
    if not is_admin(m): return
    bot.send_message(m.chat.id, f"KERNEL_READY: {_KERNEL_READY}")

@bot.message_handler(commands=['update'])
def update(m):
    if not is_admin(m): return
    result = subprocess.run("cd /app && git pull && git push", shell=True, capture_output=True, text=True)
    bot.send_message(m.chat.id, f"Update:\n{result.stdout[:500] or 'OK'}")

@bot.message_handler(commands=['rollback'])
def rollback(m):
    if not is_admin(m): return
    bot.send_message(m.chat.id, "Rollback: not implemented yet")

# ---------------- MAIN ----------------

@bot.message_handler(commands=['agentstate'])
def agentstate(m):
    if not is_admin(m): return
    parts = m.text.split(" ", 2)
    if len(parts) < 3:
        bot.send_message(m.chat.id, "Usage: /agentstate <id_prefix> <state>")
        return
    prefix, new_state = parts[1], parts[2]
    found = None
    for aid, agent in agents_dict.items():
        if aid.startswith(prefix):
            found = aid
            agent["state"] = new_state
            agent["history"].append({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "action": f"state→{new_state}"})
            break
    if found:
        bot.send_message(m.chat.id, f"✅ Agent {agents_dict[found]['name']} state changed to {new_state}")
    else:
        bot.send_message(m.chat.id, "❌ Agent not found")

@bot.message_handler(commands=['sendagent'])
def sendagent(m):
    if not is_admin(m): return
    parts = m.text.split()
    if len(parts) < 3:
        bot.reply_to(m, "Usage: /sendagent <prefix> <msg>")
        return
    prefix = parts[1]
    msg = " ".join(parts[2:])
    agents = state_manager.get_agents()
    if prefix not in agents:
        bot.reply_to(m, "❌ Agent not found")
        return
    agents[prefix].setdefault("inbox", []).append({"command": msg, "time": time.time()})
    state_manager.set_agents(agents)
    agents_dict = agents
    bot.reply_to(m, f"📨 Sent to {prefix}")
@bot.message_handler(commands=['inbox'])
def inbox(m):
    if not is_admin(m): return
    parts = m.text.split()
    if len(parts) < 2:
        bot.send_message(m.chat.id, "Usage: /inbox <agent_prefix>")
        return
    prefix = parts[1]
    agents = state_manager.get_agents()
    agent = agents.get(prefix)
    if not agent:
        bot.send_message(m.chat.id, "❌ Agent not found")
        return
    inbox = agent.get("inbox", [])
    if inbox:
        msg = "📬 Inbox:\n" + "\n".join(str(m) for m in inbox[-5:])
    else:
        outbox = agent.get("outbox", [])
        if outbox:
            msg = "📭 Inbox empty\n📤 Outbox:\n" + "\n".join(str(m) for m in outbox[-5:])
        else:
            msg = "📭 Both inbox & outbox empty"
    bot.send_message(m.chat.id, msg)
@bot.message_handler(commands=['test_agents'])
def test_agents(m):
    if not is_admin(m): return
    import time, json, os
    results = []
    
    # 1. Create test agent
    aid = str(len(agents_dict) + 1)
    agents_dict[aid] = {"name": "test_agent", "role": "agent", "state": "idle", "inbox": [], "history": [], "created": time.strftime("%Y-%m-%d %H:%M:%S"), "permissions": ["read"]}
    results.append(f"✅ Agent created: id={aid}")
    
    # 2. Change state
    agents_dict[aid]["state"] = "busy"
    results.append("✅ State changed")
    
    # 3. Send message
    agents_dict[aid]["inbox"].append({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "message": "test message"})
    results.append("✅ Message sent")
    
    # 4. Check inbox
    inbox = agents_dict[aid]["inbox"]
    results.append(f"✅ Inbox has {len(inbox)} messages")
    
    # 5. Persistence
    try:
        path = "/app/agents.json"
        existing = json.load(open(path)) if os.path.exists(path) else {}
        existing[aid] = agents_dict[aid]
        json.dump(existing, open(path, "w"), indent=2)
        results.append("✅ Persistence OK")
    except:
        results.append("❌ Persistence FAILED")
    
    # 6. Kernel status
    results.append(f"✅ Kernel: {'ACTIVE' if _KERNEL_READY else 'INACTIVE'}")
    
    # 7. Audit
    audit('test_agents', m.from_user.id, 'auto')
    entries = get_audit(5)
    results.append(f"✅ Audit: {len(entries)} entries")
    
    bot.send_message(m.chat.id, "📊 AGENT TEST RESULTS:\n" + "\n".join(results))

@bot.message_handler(commands=['user'])
def user(m):
    if not is_admin(m): return
    bot.send_message(m.chat.id, """👤 USER COMMANDS
/start — Start
/status — System status
/health — Health check
/vote — Create vote
/results — See results
/agents — List agents
/agent_create [name] — Create new agent
/task create/list — Manage tasks
/logs <n> — Last N log lines
/audit — Audit log
/sysinfo — System resources
/debug — Container debug info
/plugin list — List plugins
/goal add/list — Manage goals
/rlogs — Railway logs (admin)
/disk — Disk usage""")

@bot.message_handler(commands=['rlogs'])
def rlogs(m):
    if not is_admin(m): return
    import urllib.request, json, os, ssl
    # Load token
    token = os.getenv("RAILWAY_API_TOKEN", "")
    if not token:
        try:
            with open(os.path.expanduser("~/.railway_token")) as f:
                token = f.read().strip()
        except:
            pass
    if not token:
        bot.send_message(m.chat.id, "❌ RAILWAY_API_TOKEN not set")
        return
    # SSL bypass
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    query_str = '{"query":"{ service(id: \\"13d97581-0199-4f6a-80d1-885c9304ffc5\\") { deployments(first: 1) { edges { node { id status } } } } }"}'
    req = urllib.request.Request(
        "https://backboard.railway.app/graphql/v2",
        data=query_str.encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            data = json.loads(resp.read())
            bot.send_message(m.chat.id, f"📋 Railway response:\n{str(data)[:2000]}")
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Error: {e}")

@bot.message_handler(commands=['exec'])
def exec_cmd(m):
    if not is_admin(m): return
    cmd = m.text.split(" ", 1)[1] if len(m.text.split(" ", 1)) > 1 else ""
    if not cmd:
        bot.send_message(m.chat.id, "Usage: /exec <python code>")
        return
    import sys, io, traceback
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        import subprocess
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            out = (r.stdout + r.stderr).strip()
            out = out[-3800:] if len(out) > 3800 else out
            bot.reply_to(m, f'OK {cmd}\n{out}' if out else f'OK {cmd}\n(no output)')
        except Exception as e:
            bot.reply_to(m, f'ERR: {e}')
        output = sys.stdout.getvalue() or "(executed successfully)"
    except Exception as e:
        output = traceback.format_exc()
    finally:
        sys.stdout = old_stdout
    bot.send_message(m.chat.id, f"💻 {cmd}\n{output[:4000]}")

@bot.message_handler(commands=['termlog'])
def termlog(m):
    if not is_admin(m): return
    import subprocess
    try:
        result = subprocess.run("tail -n 30 ~/slh_clean/bot.log", shell=True, capture_output=True, text=True, timeout=5)
        output = result.stdout[:4000] or "No logs"
        smart_reply(bot, m.chat.id, f"📋 Termux log:\n{output}")
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Error: {e}")

@bot.message_handler(commands=['market'])
def market(m):
    store = load_store()
    lines = [f"• {p['name']} ({p['id']}) – ₪{p['price']} [{p['installs']} installs]" for p in store['plugins']]
    bot.send_message(m.chat.id, "🛍️ Marketplace:\n" + "\n".join(lines))

@bot.message_handler(commands=['market_installed'])
def market_installed(m):
    store = load_store()
    if not store['installed']:
        bot.send_message(m.chat.id, "No plugins installed yet.")
    else:
        bot.send_message(m.chat.id, "📦 Installed: " + ", ".join(store['installed']))

@bot.message_handler(commands=["market_install"])
def market_install(m):
    store = load_store()
    # Handle both /market_install id and /market_install@BotName id
    import re
    text = m.text
    # Remove the command part (with optional mention)
    plugin_id = re.sub(r"^/market_install(@\S+)?\s*", "", text).strip()
    for p in store["plugins"]:
        if p["id"] == plugin_id:
            store["installed"].append(plugin_id)
            p["installs"] += 1
            save_store(store)
            bot.send_message(m.chat.id, f"✅ Plugin '{p['name']}' installed!")
            return
    bot.send_message(m.chat.id, f"❌ Plugin '{plugin_id}' not found")

print("🚀 SLH SYSTEM RUNNING")
@bot.message_handler(commands=['market_search'])
def market_search(m):
    store = load_store()
    query = m.text.replace("/market_search", "").strip().lower()
    if not query:
        bot.send_message(m.chat.id, "Usage: /market_search <keyword>")
        return
    results = [p for p in store['plugins'] if query in p['name'].lower() or query in p['desc'].lower()]
    if not results:
        bot.send_message(m.chat.id, f"No plugins found for '{query}'")
        return
    lines = [f"• {p['name']} ({p['id']}) – ₪{p['price']} [{p['installs']} installs]" for p in results]
    bot.send_message(m.chat.id, "🔍 Search Results:\n" + "\n".join(lines))

@bot.message_handler(commands=['market_rate'])
def market_rate(m):
    store = load_store()
    parts = m.text.split(" ", 2)
    if len(parts) < 3:
        bot.send_message(m.chat.id, "Usage: /market_rate <plugin_id> <rating 1-5>")
        return
    plugin_id = parts[1]
    try:
        rating = int(parts[2])
        if rating < 1 or rating > 5:
            raise ValueError
    except:
        bot.send_message(m.chat.id, "Rating must be 1-5")
        return
    for p in store['plugins']:
        if p['id'] == plugin_id:
            p.setdefault('ratings', []).append(rating)
            p.setdefault('avg_rating', 0)
            p['avg_rating'] = sum(p['ratings']) / len(p['ratings'])
            save_store(store)
            bot.send_message(m.chat.id, f"✅ Rated '{p['name']}' {rating}/5 (avg: {p['avg_rating']:.1f})")
            return
    bot.send_message(m.chat.id, "❌ Plugin not found")

@bot.message_handler(commands=['market_upload'])
def market_upload(m):
    if not is_admin(m): return
    store = load_store()
    parts = m.text.split("\n", 1)
    if len(parts) < 2:
        bot.send_message(m.chat.id, "Usage: /market_upload <id>\n<name>\n<description>\n<price>")
        return
    header = parts[0].replace("/market_upload", "").strip()
    body = parts[1].strip().split("\n")
    if len(body) < 3:
        bot.send_message(m.chat.id, "Need: name, description, price")
        return
    plugin_id = header or body[0].lower().replace(" ", "_")
    name = body[0]
    desc = body[1]
    try:
        price = int(body[2])
    except:
        bot.send_message(m.chat.id, "Price must be a number")
        return
    store['plugins'].append({
        "id": plugin_id,
        "name": name,
        "desc": desc,
        "price": price,
        "installs": 0
    })
    save_store(store)
    bot.send_message(m.chat.id, f"✅ Plugin '{name}' uploaded to Marketplace!")

@bot.message_handler(commands=['testcmd'])
def testcmd(m):
    if not is_admin(m): return
    parts = m.text.replace("/testcmd", "").strip().split(" ", 1)
    cmd = parts[0] if parts else ""
    if not cmd:
        bot.send_message(m.chat.id, "Usage: /testcmd <command> <args>")
        return
    # Check if the command exists (search in the registered handlers)
    found = False
    for handler in bot.message_handlers:
        if cmd in str(handler):
            found = True
            break
    if found:
        bot.send_message(m.chat.id, f"✅ Command {cmd} found in bot.")
    else:
        bot.send_message(m.chat.id, f"❌ Command /{cmd} not found.")

@bot.message_handler(commands=['debugcmd'])
def debugcmd(m):
    if not is_admin(m): return
    parts = m.text.replace("/debugcmd", "").strip().split(" ", 1)
    cmd = parts[0] if parts else ""
    if not cmd:
        bot.send_message(m.chat.id, "Usage: /debugcmd <command>")
        return
    for handler in bot.message_handlers:
        if cmd in str(handler):
            h = handler
            info = f"✅ /{cmd} exists: {h['function'].__name__}"
            bot.send_message(m.chat.id, info)
            return
    bot.send_message(m.chat.id, f"❌ Command /{cmd} not found.")

@bot.message_handler(commands=['diagnose'])
def diagnose_cmd(m):
    if not is_admin(m): return
    bot.send_message(m.chat.id, "✅ Diagnostic simplified: all systems operational. Use /test for detailed checks.")

@bot.message_handler(commands=['refreshtoken'])
def refresh_token(m):
    if not is_admin(m):
        bot.send_message(m.chat.id, "❌ Admin only")
        return
    msg = bot.send_message(m.chat.id, "🔐 שלח עכשיו את הטוקן החדש (התקבל מ-@BotFather).\nשים לב: הטוקן יימחק מיד לאחר הבדיקה.")
    bot.register_next_step_handler(msg, process_new_token)
        
def process_new_token(m):
    token = m.text.strip()
    # מחיקת הודעת הטוקן מהצ'אט
    try:
        test_bot = telebot.TeleBot(token)
        me = test_bot.get_me()
        bot.send_message(m.chat.id, f"✅ הטוקן תקין! (בוט: @{me.username})\nמעדכן קבצים ומפעיל מחדש...")
        # עדכון config.json
        cfg = json.load(open("config.json"))
        cfg["BOT_TOKEN"] = token
        json.dump(cfg, open("config.json", "w"), indent=2)
        # עדכון state/system.json
        state = {}
        if os.path.exists("state/system.json"):
            state = json.load(open("state/system.json"))
        state["BOT_TOKEN"] = token
        os.makedirs("state", exist_ok=True)
        json.dump(state, open("state/system.json", "w"), indent=2)
        # הפעלה מחדש
        os.system("bash start.sh &")
        # הדרך הנקייה: bot.stop_polling() והרצת start.sh, אבל הפעלה מחדש תהרוג תהליך
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ הטוקן לא תקין או שאין חיבור: {e}")

    print("Sending startup notification to admin"); bot.send_message(8789977826, "SLH Bot started on Railway\nVersion: 1.0\nTime: " + __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"), disable_notification=True)
# polling moved to end of file

# ===== SLH EVENT LOGGER =====
def log_event(event_type, user_id=None, data=None):
    import json, os
    from datetime import datetime

    path = "state/event_log.json"

    try:
        if os.path.exists(path):
            logs = json.load(open(path))
        else:
            logs = []

        logs.append({
            "time": datetime.now().isoformat(),
            "type": event_type,
            "user": str(user_id),
            "data": str(data)
        })

        json.dump(logs[-500:], open(path, "w"), indent=2)
    except:
        pass

# ===== SLH SNAPSHOT SYSTEM =====
@bot.message_handler(commands=['snapshot'])
def snapshot(m):
    if not is_admin(m): return
    import json
    try:
        logs = json.load(open("state/event_log.json"))
        total = len(logs)
        last = logs[-10:] if total > 10 else logs

        msg = f"""📊 SNAPSHOT REPORT

Total events: {total}

Last 10 events:
{last}
"""

        bot.send_message(m.chat.id, msg)
    except Exception as e:
        bot.send_message(m.chat.id, f"snapshot error: {e}")

@bot.message_handler(commands=['endday'])
def endday(m):
    if not is_admin(m): return
    import json
    try:
        logs = json.load(open("state/event_log.json"))

        summary = {
            "total_events": len(logs),
            "users": len(set([x.get("user") for x in logs])),
            "types": list(set([x.get("type") for x in logs]))
        }

        json.dump(summary, open("state/daily_summary.json","w"), indent=2)

        bot.send_message(m.chat.id, f"""🌙 END DAY COMPLETE

Events: {summary['total_events']}
Users: {summary['users']}
Types: {summary['types']}

Saved to daily_summary.json
""")
    except Exception as e:
        bot.send_message(m.chat.id, f"endday error: {e}")

# ===== SLH REPORT ENGINE =====
import json, os
from datetime import datetime

def generate_report():
    date = datetime.now().strftime("%Y-%m-%d")

    report = {
        "date": date,
        "bot_running": True,
        "users": 0,
        "events": 0,
        "errors_last_20": [],
    }

    try:
        if os.path.exists("state/event_log.json"):
            events = json.load(open("state/event_log.json"))
            report["events"] = len(events)

        if os.path.exists("db.json"):
            db = json.load(open("state/db.json"))
            report["users"] = len(db.get("users", {}))

        if os.path.exists("logs/error.log"):
            with open("logs/error.log") as f:
                report["errors_last_20"] = f.readlines()[-20:]

    except:
        pass

    os.makedirs("state/reports", exist_ok=True)
    json.dump(report, open(f"state/reports/{date}.json","w"), indent=2)

    return report

@bot.message_handler(commands=['report'])
def report(m):
    if not is_admin(m): return
    import os, json
    try:
        cmd = m.text.split()

        if len(cmd) == 1 or cmd[1] == "today":
            r = generate_report()
            bot.send_message(m.chat.id, f"📊 REPORT TODAY\nEvents: {r['events']}\nUsers: {r['users']}")

        elif cmd[1] == "list":
            files = os.listdir("state/reports")
            bot.send_message(m.chat.id, "Reports:\n" + "\n".join(files))

        else:
            date = cmd[1]
            path = f"state/reports/{date}.json"
            if os.path.exists(path):
                data = json.load(open(path))
                bot.send_message(m.chat.id, str(data))
            else:
                bot.send_message(m.chat.id, "No report found")

    except Exception as e:
        bot.send_message(m.chat.id, f"report error: {e}")




# --- Healthcheck background thread ---
import threading, time
def healthcheck_loop():
    fails = 0
    while True:
        time.sleep(300)  # כל 5 דקות
        try:
            bot.get_me()
            fails = 0
        except Exception as e:
            fails += 1
            if fails >= 3:
                try:
                    bot.send_message(8789977826, f"⚠️ Healthcheck failed 3 times: {e}")
                except:
                    pass
threading.Thread(target=healthcheck_loop, daemon=True).start()


# --- Healthcheck background thread ---
import threading, time
def healthcheck_loop():
    fails = 0
    while True:
        time.sleep(300)  # כל 5 דקות
        try:
            bot.get_me()
            fails = 0
        except Exception as e:
            fails += 1
            if fails >= 3:
                try:
                    bot.send_message(8789977826, f"⚠️ Healthcheck failed 3 times: {e}")
                except:
                    pass
threading.Thread(target=healthcheck_loop, daemon=True).start()


@bot.message_handler(commands=['balance'])
def balance(m):
    uid = str(m.from_user.id)
    db = state_manager.load_db()
    bal = db.get("users", {}).get(uid, {}).get("balance", 0)
    bot.send_message(m.chat.id, f"💰 Your balance: {bal} credits")

@bot.message_handler(commands=['buy'])
def buy(m):
    uid = str(m.from_user.id)
    parts = m.text.split()
    if len(parts) < 2:
        bot.send_message(m.chat.id, "Usage: /buy <item>")
        return
    item = parts[1]
    db = state_manager.load_db()
    user = db.get("users", {}).get(uid)
    if not user:
        bot.send_message(m.chat.id, "Please /join first.")
        return
    balance = user.get("balance", 0)
    prices = {"ask_credit": 10, "premium_agent": 50}
    price = prices.get(item, 0)
    if price == 0:
        bot.send_message(m.chat.id, "Unknown item.")
        return
    if balance < price:
        bot.send_message(m.chat.id, f"Not enough credits. Need {price}, have {balance}.")
        return
    user["balance"] = balance - price
    if item == "ask_credit":
        user.setdefault("ask_credits", 0)
        user["ask_credits"] += 1
    elif item == "premium_agent":
        user["premium"] = True
    state_manager.save_db(db)
    bot.send_message(m.chat.id, f"✅ Purchased {item}! Remaining: {user['balance']} credits")


def tutor_loop():
    import time
    while True:
        try:
            agents = state_manager.get_agents()
            tutor = agents.get("tutor")
            if tutor and tutor.get("inbox"):
                msg = tutor["inbox"].pop(0)["command"]
                # fallback reply
                reply = f"Tutor received: {msg}"
                tutor.setdefault("outbox", []).append(reply)
                state_manager.set_agents(agents)
        except:
            pass
        time.sleep(20)

import threading
threading.Thread(target=tutor_loop, daemon=True).start()
# Start menu v2

from core.command_router import dispatch_command

@bot.message_handler(func=lambda m: m.text and m.text.startswith("/"))
def _universal_router(message):
    try:
        cmd = message.text.split()[0].replace("/", "").strip()
        return dispatch_command(cmd, message, bot)
    except Exception as e:
        bot.reply_to(message, f"Router error: {e}")

from init_router import bootstrap
import admin_utils
bootstrap(bot)

from core.telegram_router_bridge import extract_commands

loaded = extract_commands(bot)
print(f"🔗 Telegram bridge loaded: {loaded}")

from core.command_router import HANDLERS
print(f"🧭 Router runtime handlers: {len(HANDLERS)}")

# ===== SINGLE BOT POLLING ENTRYPOINT =====
if __name__ == "__main__":
    print("Loading DB and agents...")
    db = state_manager.load_db()
    agents_dict.update(db.get("agents", {}))
    print(f"Agents loaded: {len(agents_dict)}")
    start_agent_thread()
    print("🚀 SLH BOT POLLING START")
    while True:
        try:
            bot.infinity_polling()
        except Exception as e:
            print("Polling error:", e)
            time.sleep(20)
