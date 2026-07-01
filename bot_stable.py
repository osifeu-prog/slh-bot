import os, sys, json, time, subprocess
from internal_agent import start_agent_thread
import telebot
from marketplace import load_store, save_store
from datetime import datetime
from audit_logger import audit, get_audit
from core.event_bus import EventBus
from plugins.task import TaskPlugin
import welcome_handler
import course_handlers
import learn_handlers
import project_commands
import monitor_handler
import ask_handler
import complete_handler
import diagnostic_handler
import report_handler
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
try:
    with open("config.json") as f:
        cfg = json.load(f)
except:
    cfg = {}
SUPER_ADMIN = cfg.get("SUPER_ADMIN", 8789977826)
DB_FILE = cfg.get("DB_FILE", "db.json")

bot = telebot.TeleBot(TOKEN)

# Runtime state initialization (volumes mount empty at runtime, not build time)
os.makedirs("state", exist_ok=True)
if not os.path.exists("state/db.json"):
    with open("state/db.json", "w") as _f:
        json.dump({"users": {}, "votes": {"yes": 0, "no": 0, "unsure": 0}}, _f)
for _fname, _default in [("event_log.json", []), ("progress.json", {}), ("system.json", {}), ("users.json", {})]:
    _path = f"state/{_fname}"
    if not os.path.exists(_path):
        with open(_path, "w") as _f:
            json.dump(_default, _f)


import json as _json_auth
try:
    with open("allowed_ids.json") as _f:
        _ALLOWED = _json_auth.load(_f)
except Exception:
    _ALLOWED = {"admin": 8789977826, "allowed": [8789977826]}

def is_admin(m):
    uid = m.from_user.id
    if uid not in _ALLOWED.get("allowed", []) and uid != _ALLOWED.get("admin"):
        bot.send_message(m.chat.id, "⛔ Unauthorized - admin only")
        return False
    return True



def smart_reply(bot, chat_id, text, max_len=3800):
    if len(text) <= max_len:
        bot.send_message(chat_id, text)
        return
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    parts = len(text) // max_len + 1
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton(f"Send as {parts} messages", callback_data=f"split_msg_{chat_id}"),
        InlineKeyboardButton("Download as .txt", callback_data=f"dl_msg_{chat_id}")
    )
    bot.send_message(chat_id, f"Message is {len(text)} chars. Choose:", reply_markup=markup)
    import tempfile
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
    tmp.write(text)
    tmp.close()
    if not hasattr(bot, "_msg_files"):
        bot._msg_files = {}
    bot._msg_files[chat_id] = tmp.name


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

welcome_handler.init(bot)
course_handlers.register_course_handlers(bot)
learn_handlers.register(bot)
project_commands.register(bot)
monitor_handler.init(bot)
ask_handler.init(bot)
report_handler.init(bot)
junk_handler.init(bot)
refresh_token_handler.init(bot)
smart_leaderboard.register(bot)
agents_dict = {}
start_agent_thread()

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
    kernel = type('KernelStub', (), {'state': {}, 'bus': bus, 'telegram': None})()
    TaskPlugin().on_start(kernel)
    _KERNEL_READY = True
    print("✅ Kernel modules loaded")
except Exception as e:
    print("Kernel init failed:", e)
    _KERNEL_READY = False

# ---------------- DB ----------------
BASE_DB = {"users": {}, "agents": {}, "tasks": {}, "memory": {}, "votes": {"yes": 0, "no": 0, "unsure": 0}}

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
    try:
        db = ensure_user(load_db(), m.from_user.id)
        save_db(db)
        audit('start', m.from_user.id)
        bot.send_message(m.chat.id, "🚀 SLH SYSTEM ONLINE\n/admin for control")
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Error: {e}")

@bot.message_handler(commands=['admin'])
def admin(m):
    bot.send_message(m.chat.id, """🔧 ADMIN CONTROL PANEL
📊 DIAGNOSTICS:
/test — Run full system diagnostic\n/test_agents — Quick agent self-test
/status — System status
/health — Health check
🤖 AGENTS:
/agents — List all agents
/agent_create [name] — Create new agent\n/agentstate <prefix> <state> — Change agent state\n/sendagent <prefix> <msg> — Send message to agent\n/inbox <prefix> — Check agent inbox\n/agentstate <prefix> <state> — Change agent state\n/sendagent <prefix> <msg> — Send message to agent\n/inbox <prefix> — Check agent inbox
🗳️ VOTING:
/vote — Create vote
/results — See results
💰 REVENUE:
/revenue — Revenue status
🔄 SYSTEM:
/backup — Git backup now
/restart — Restart bot
/logs <n> — Last N log lines
/clean — Clean temp files
📈 ANALYTICS:
/audit — Audit log
/memory — Memory status
/debug — Container debug info
/termux — Show Termux status
/deploy — Trigger Railway deploy
/errors — Show recent errors
/plugin list — List plugins
/goal add/list — Manage goals
/exec <cmd> — Run shell command (admin)\n/termlog — Show Termux logs (admin)\n/rlogs — Railway logs (admin)
/disk — Disk usage
/sysinfo — System resources""")

@bot.message_handler(commands=['status'])
def status(m):
    db = load_db()
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
        kernel.bus.emit("task_create", {"chat": m.chat.id, "task": parts[2] if len(parts) > 2 else ""})
    elif parts[1] == "list":
        kernel.bus.emit("task_list", {"chat": m.chat.id})

@bot.message_handler(commands=['agent_create'])
@bot.message_handler(commands=['agent_create'])
@bot.message_handler(commands=["agent_create"])
def agent_create(m):
    if not is_admin(m): return
    parts = m.text.split()
    if len(parts) < 2:
        bot.send_message(m.chat.id, "Usage: /agent_create <name>")
        return
    name = parts[1]
    try:
        with open("db.json") as f:
            db = json.load(f)
    except:
        db = {}
    agents = db.setdefault("agents", {})
    if name in agents:
        bot.send_message(m.chat.id, "❌ Agent already exists")
        return
    agents[name] = {"inbox": [], "outbox": [], "state": "idle"}
    with open("db.json", "w") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
    agents_dict.clear()
    agents_dict.update(agents)
    bot.send_message(m.chat.id, f"✅ Agent created: {name}")
@bot.message_handler(commands=['agents'])
def agents_list(m):
    if not agents_dict:
        bot.send_message(m.chat.id, "No agents yet")
    else:
        lines = [f"{v['name']} [{v.get('state','idle')}] – {v.get('role','?')}" for k, v in agents_dict.items()]
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
    db = ensure_user(load_db(), m.from_user.id)
    key = m.text.split(" ", 1)[1] if len(m.text.split(" ", 1)) > 1 else ""
    if key in db["votes"]:
        db["votes"][key] += 1
    else:
        db["votes"][key] = 1
    save_db(db)
    bot.send_message(m.chat.id, f"Voted {key}")

@bot.message_handler(commands=['results'])
def results(m):
    db = load_db()
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
        bot.send_message(m.chat.id, result.stdout[:2000] or "No logs yet")
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
@bot.message_handler(commands=['sendagent'])
@bot.message_handler(commands=['sendagent'])
@bot.message_handler(commands=['sendagent'])
@bot.message_handler(commands=['sendagent'])
@bot.message_handler(commands=['sendagent'])
def sendagent(m):
    if not is_admin(m): return
    parts = m.text.split()
    if len(parts) < 3:
        bot.reply_to(m, "Usage: /sendagent <prefix> <msg>")
        return
    prefix = parts[1]
    msg = " ".join(parts[2:])
    try:
        with open("db.json") as f:
            db = json.load(f)
    except:
        db = {}
    agents = db.setdefault("agents", {})
    if prefix not in agents:
        bot.reply_to(m, "❌ Agent not found")
        return
    cmd = msg.split()[0].lower() if msg else ""
    if cmd == "ask":
        prompt = " ".join(msg.split()[1:]) if len(msg.split()) > 1 else ""
        data = {"command": "ask", "prompt": prompt, "time": time.time()}
    agents[prefix].setdefault("inbox", []).append({"command": msg, "time": time.time()})
    with open("db.json", "w") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
    agents_dict.clear()
    agents_dict.update(agents)
    bot.reply_to(m, f"📨 Sent to {prefix}")
@bot.message_handler(commands=['inbox'])
def inbox(m):
    if not is_admin(m): return
    parts = m.text.split()
    if len(parts) < 2:
        bot.send_message(m.chat.id, "Usage: /inbox <agent_prefix>")
        return
    prefix = parts[1]
    try:
        with open("db.json") as f:
            db = json.load(f)
        agent = db.get("agents", {}).get(prefix)
        if not agent:
            bot.send_message(m.chat.id, "❌ Agent not found")
            return
        outbox = agent.get("outbox", [])
        if outbox:
            msg = "📬 Outbox:\n" + "\n".join(outbox[-5:])
        else:
            msg = "📭 Outbox empty"
    except Exception as e:
        msg = f"Error reading db: {e}"
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
    # Admin only
    if str(m.from_user.id) != str(SUPER_ADMIN):
        bot.send_message(m.chat.id, "❌ Admin only")
        return
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
    if str(m.from_user.id) != str(SUPER_ADMIN):
        bot.send_message(m.chat.id, "❌ Admin only")
        return
    cmd = m.text.split(" ", 1)[1] if len(m.text.split(" ", 1)) > 1 else ""
    if not cmd:
        bot.send_message(m.chat.id, "Usage: /exec <shell command>")
        return
    import subprocess
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        output = result.stdout[:2000] or result.stderr[:500] or "No output"
        smart_reply(bot, m.chat.id, f"💻 {cmd}\n{output}")
    except subprocess.TimeoutExpired:
        bot.send_message(m.chat.id, "⏰ Command timed out")
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Error: {e}")


@bot.message_handler(commands=['termlog'])
def termlog(m):
    if not is_admin(m): return
    if str(m.from_user.id) != str(SUPER_ADMIN):
        bot.send_message(m.chat.id, "❌ Admin only")
        return
    import subprocess
    try:
        result = subprocess.run("tail -n 30 ~/slh_clean/bot.log", shell=True, capture_output=True, text=True, timeout=5)
        output = result.stdout[:2000] or "No logs"
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
    import os, py_compile
    cwd = os.path.expanduser("~/slh_clean")
    issues = []
    bot_path = os.path.join(cwd, "bot.py")
    
    if os.path.exists(bot_path):
        issues.append("✅ bot.py exists")
        try:
            py_compile.compile(bot_path, doraise=True)
            issues.append("✅ Syntax OK")
        except py_compile.PyCompileError as e:
            issues.append(f"❌ Syntax error: {e}")
    else:
        issues.append("❌ bot.py missing")
    
    # Check for handler placement
    with open(bot_path) as f:
        code = f.read()
    loop_pos = code.find("while True:")
    if loop_pos != -1:
        after_loop = code[loop_pos:]
        if "@bot.message_handler" in after_loop:
            import re
            handlers = re.findall(r"@bot\.message_handler\(commands=\['(\w+)'\]\)", after_loop)
            if handlers:
                issues.append(f"⚠️ Handlers after while True: {', '.join('/'+h for h in handlers)}")
            else:
                issues.append("✅ No handlers after while True")
        else:
            issues.append("✅ No handlers after while True")
    else:
        issues.append("❌ while True loop not found")
    
    # Check DB
    db_path = os.path.join(cwd, "db.json")
    if os.path.exists(db_path):
        issues.append("✅ db.json exists")
    else:
        issues.append("❌ db.json missing")
    
    if any("❌" in i or "⚠️" in i for i in issues):
        issues.insert(0, "⚠️ Issues found:")
    else:
        issues.insert(0, "✅ All checks passed")
    
    bot.send_message(m.chat.id, "\n".join(issues))


while True:
    try:
        
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
                bot.delete_message(m.chat.id, m.message_id)
            except:
                pass
            # בדיקת תקינות
            if ":" not in token or len(token) < 20:
                bot.send_message(m.chat.id, "❌ פורמט לא תקין. נסה שוב /refreshtoken")
                return
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
                bot.delete_message(m.chat.id, m.message_id)
            except:
                pass
            # בדיקת תקינות
            if ":" not in token or len(token) < 20:
                bot.send_message(m.chat.id, "❌ פורמט לא תקין. נסה שוב /refreshtoken")
                return
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
        bot.infinity_polling() # שנה לכתובת שלך
    except Exception as e:
        print("Polling error:", e)
        time.sleep(5)


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


@bot.message_handler(commands=['logs'])
def logs(m):
    try:
        with open("logs/error.log") as f:
            data = f.readlines()[-20:]
        bot.send_message(m.chat.id, "".join(data))
    except Exception as e:
        bot.send_message(m.chat.id, str(e))


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
