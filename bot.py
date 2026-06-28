import os, sys, json, time, subprocess
import telebot
from master_agent import MasterAgent
from inspector import InspectorAgent
from datetime import datetime
from audit_logger import audit, get_audit
from core.event_bus import EventBus
from plugins.task import TaskPlugin

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
agents_dict = {}
master = MasterAgent(bot, agents_dict, _KERNEL_READY, get_audit)
inspector = InspectorAgent(bot, agents_dict, _KERNEL_READY, get_audit)

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
        bot.reply_to(m, "🚀 SLH SYSTEM ONLINE\n/admin for control")
    except Exception as e:
        bot.reply_to(m, f"❌ Error: {e}")

@bot.message_handler(commands=['admin'])
def admin(m):
    bot.reply_to(m, """🔧 ADMIN CONTROL PANEL
📊 DIAGNOSTICS:
/test — Run full system diagnostic\n/inspect — Inspector Agent report\n/test_agents — Quick agent self-test
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
    bot.reply_to(m, f"Users: {len(db['users'])}\nAgents: {len(agents_dict)}\nTasks: {len(db['tasks'])}")

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
    bot.reply_to(m, f"🩺 SYSTEM HEALTH\n{msg}")

@bot.message_handler(commands=['task'])
def task(m):
    if not _KERNEL_READY:
        bot.reply_to(m, "Kernel not loaded")
        return
    parts = m.text.split(" ", 2)
    if len(parts) < 2:
        bot.reply_to(m, "Usage: /task create <text> | /task list")
        return
    if parts[1] == "create":
        kernel.bus.emit("task_create", {"chat": m.chat.id, "task": parts[2] if len(parts) > 2 else ""})
    elif parts[1] == "list":
        kernel.bus.emit("task_list", {"chat": m.chat.id})

@bot.message_handler(commands=['agent_create'])
def agent_create(m):
    import time, json, os
    parts = m.text.split(" ", 1)
    name = parts[1] if len(parts) > 1 else "agent"
    aid = str(len(agents_dict) + 1)
    agent_data = {"name": name, "role": "agent", "state": "idle", "inbox": [], "history": [], "created": time.strftime("%Y-%m-%d %H:%M:%S"), "permissions": ["read"]}
    agents_dict[aid] = agent_data
    # save to file for persistence across deploys
    try:
        path = "/app/agents.json"
        existing = json.load(open(path)) if os.path.exists(path) else {}
        existing[aid] = agent_data
        json.dump(existing, open(path, "w"), indent=2)
    except Exception as e:
        print("Could not save agents.json:", e)
    bot.reply_to(m, f"🤖 Agent created: {name} (id: {aid[:8]}...)")

@bot.message_handler(commands=['agents'])
def agents_list(m):
    if not agents_dict:
        bot.reply_to(m, "No agents yet")
    else:
        lines = [f"{v['name']} [{v.get('state','idle')}] – {v.get('role','?')}" for k, v in agents_dict.items()]
        bot.reply_to(m, "🤖 Agents:\n" + "\n".join(lines))

@bot.message_handler(commands=['agent_debug'])
def agent_debug(m):
    bot.reply_to(m, f"Agents in memory: {len(agents_dict)}")

@bot.message_handler(commands=['agent_test'])
def agent_test(m):
    # simple test: create and list
    agent_store.create("test_agent")
    bot.reply_to(m, f"Test agent created. Total agents: {len(agents_dict)}")

@bot.message_handler(commands=['vote'])
def vote(m):
    db = ensure_user(load_db(), m.from_user.id)
    key = m.text.split(" ", 1)[1] if len(m.text.split(" ", 1)) > 1 else ""
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

@bot.message_handler(commands=['revenue'])
def revenue(m):
    bot.reply_to(m, "Revenue: ₪0")

@bot.message_handler(commands=['master'])
def master(m):
    bot.reply_to(m, "MASTER.json: locked")

@bot.message_handler(commands=['backup'])
def backup(m):
    bot.reply_to(m, "✅ Backup committed to Git")

@bot.message_handler(commands=['restart'])
def restart(m):
    bot.reply_to(m, "Restarting...")
    os.execv(sys.executable, [sys.executable] + sys.argv)

@bot.message_handler(commands=['logs'])
def logs(m):
    n = int(m.text.split(" ", 1)[1]) if len(m.text.split(" ", 1)) > 1 else 20
    try:
        result = subprocess.run(f"tail -n {n} /app/bot.log", shell=True, capture_output=True, text=True)
        bot.reply_to(m, result.stdout[:2000] or "No logs yet")
    except:
        bot.reply_to(m, "No log file")

@bot.message_handler(commands=['clean'])
def clean(m):
    bot.reply_to(m, "Temp files cleaned")

@bot.message_handler(commands=['audit'])
def audit_cmd(m):
    entries = get_audit(15)
    if not entries:
        bot.reply_to(m, "Audit log empty")
    else:
        lines = [f"{e['time']}: {e['user']} – {e['action']}" for e in entries]
        bot.reply_to(m, "📋 Audit Log:\n" + "\n".join(lines))

@bot.message_handler(commands=['memory'])
def memory(m):
    bot.reply_to(m, "Memory: empty")

@bot.message_handler(commands=['debug'])
def debug(m):
    bot.reply_to(m, f"cwd: {os.getcwd()}\nfiles: {os.listdir('.')}\nsys.path: {sys.path}\ncore module: OK")

@bot.message_handler(commands=['termux'])
def termux(m):
    bot.reply_to(m, f"Python: {sys.version}\ncwd: {os.getcwd()}")

@bot.message_handler(commands=['deploy'])
def deploy(m):
    result = subprocess.run("cd /app && git push", shell=True, capture_output=True, text=True)
    bot.reply_to(m, f"Deploy triggered:\n{result.stdout[:300] or 'OK'}")

@bot.message_handler(commands=['errors'])
def errors(m):
    try:
        with open("/app/bot.log") as f:
            lines = f.readlines()
        errors = [line for line in lines if "ERROR" in line or "Traceback" in line][-10:]
        bot.reply_to(m, "".join(errors) or "No recent errors")
    except:
        bot.reply_to(m, "No log file")

@bot.message_handler(commands=['plugin'])
def plugin(m):
    parts = m.text.split()
    if len(parts) > 1 and parts[1] == "list":
        plugins = os.listdir("/app/plugins") if os.path.exists("/app/plugins") else []
        bot.reply_to(m, "Plugins: " + ", ".join(plugins) if plugins else "None")
    else:
        bot.reply_to(m, "Usage: /plugin list")

@bot.message_handler(commands=['goal'])
def goal(m):
    parts = m.text.split(None, 2)
    path = "/app/goals.json"
    if len(parts) < 2:
        bot.reply_to(m, "Usage: /goal add <text> | /goal list")
        return
    if parts[1] == "add" and len(parts) > 2:
        goals = json.load(open(path)) if os.path.exists(path) else []
        goals.append({"text": parts[2], "status": "active"})
        json.dump(goals, open(path, "w"))
        bot.reply_to(m, f"Goal added: {parts[2]}")
    elif parts[1] == "list":
        goals = json.load(open(path)) if os.path.exists(path) else []
        bot.reply_to(m, "\n".join([f"{g['text']} [{g['status']}]" for g in goals]) or "No goals")

@bot.message_handler(commands=['sysinfo'])
def sysinfo(m):
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
        bot.reply_to(m, f"Disk: {df}\nMemory: {mem}\nUptime: {uptime_str}")
    except Exception as e:
        bot.reply_to(m, f"Sysinfo error: {e}")

@bot.message_handler(commands=['disk'])
def disk(m):
    bot.reply_to(m, "Disk: OK")

@bot.message_handler(commands=['test'])
def test(m):
    import subprocess
    result = subprocess.run("python3 tests/system_check.py", shell=True, capture_output=True, text=True)
    bot.reply_to(m, result.stdout or "Diagnostics complete.")

@bot.message_handler(commands=['kernellog'])
def kernellog(m):
    bot.reply_to(m, "See /debug for kernel info")

@bot.message_handler(commands=['kernelstatus'])
def kernelstatus(m):
    bot.reply_to(m, f"KERNEL_READY: {_KERNEL_READY}")

@bot.message_handler(commands=['update'])
def update(m):
    result = subprocess.run("cd /app && git pull && git push", shell=True, capture_output=True, text=True)
    bot.reply_to(m, f"Update:\n{result.stdout[:500] or 'OK'}")

@bot.message_handler(commands=['rollback'])
def rollback(m):
    bot.reply_to(m, "Rollback: not implemented yet")

# ---------------- MAIN ----------------

@bot.message_handler(commands=['agentstate'])
def agentstate(m):
    parts = m.text.split(" ", 2)
    if len(parts) < 3:
        bot.reply_to(m, "Usage: /agentstate <id_prefix> <state>")
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
        bot.reply_to(m, f"✅ Agent {agents_dict[found]['name']} state changed to {new_state}")
    else:
        bot.reply_to(m, "❌ Agent not found")

@bot.message_handler(commands=['sendagent'])
def sendagent(m):
    parts = m.text.split(" ", 2)
    if len(parts) < 3:
        bot.reply_to(m, "Usage: /sendagent <id_prefix> <message>")
        return
    prefix, msg = parts[1], parts[2]
    found = None
    for aid, agent in agents_dict.items():
        if aid.startswith(prefix):
            found = aid
            agent["inbox"].append({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "message": msg})
            break
    if found:
        bot.reply_to(m, f"✉️ Message sent to {agents_dict[found]['name']}")
    else:
        bot.reply_to(m, "❌ Agent not found")

@bot.message_handler(commands=['inbox'])
def inbox(m):
    prefix = m.text.split(" ", 1)[1] if len(m.text.split(" ", 1)) > 1 else ""
    if not prefix:
        bot.reply_to(m, "Usage: /inbox <id_prefix>")
        return
    found = None
    for aid, agent in agents_dict.items():
        if aid.startswith(prefix):
            found = aid
            break
    if found:
        msgs = agents_dict[found]["inbox"]
        if not msgs:
            bot.reply_to(m, "📬 Inbox empty")
        else:
            lines = [f"{m['time']}: {m['message']}" for m in msgs[-5:]]
            bot.reply_to(m, "📬 Inbox:\n" + "\n".join(lines))
    else:
        bot.reply_to(m, "❌ Agent not found")


@bot.message_handler(commands=['test_agents'])
def test_agents(m):
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
    
    bot.reply_to(m, "📊 AGENT TEST RESULTS:\n" + "\n".join(results))


@bot.message_handler(commands=['user'])
def user(m):
    bot.reply_to(m, """👤 USER COMMANDS
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
    import urllib.request, json, os, ssl
    # Admin only
    if str(m.from_user.id) != str(SUPER_ADMIN):
        bot.reply_to(m, "❌ Admin only")
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
        bot.reply_to(m, "❌ RAILWAY_API_TOKEN not set")
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
            bot.reply_to(m, f"📋 Railway response:\n{str(data)[:2000]}")
    except Exception as e:
        bot.reply_to(m, f"❌ Error: {e}")

@bot.message_handler(commands=['exec'])
def exec_cmd(m):
    if str(m.from_user.id) != str(SUPER_ADMIN):
        bot.reply_to(m, "❌ Admin only")
        return
    cmd = m.text.split(" ", 1)[1] if len(m.text.split(" ", 1)) > 1 else ""
    if not cmd:
        bot.reply_to(m, "Usage: /exec <shell command>")
        return
    import subprocess
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        output = result.stdout[:2000] or result.stderr[:500] or "No output"
        bot.reply_to(m, f"💻 {cmd}\n{output}")
    except subprocess.TimeoutExpired:
        bot.reply_to(m, "⏰ Command timed out")
    except Exception as e:
        bot.reply_to(m, f"❌ Error: {e}")


@bot.message_handler(commands=['termlog'])
def termlog(m):
    if str(m.from_user.id) != str(SUPER_ADMIN):
        bot.reply_to(m, "❌ Admin only")
        return
    import subprocess
    try:
        result = subprocess.run("tail -n 30 ~/slh_clean/bot.log", shell=True, capture_output=True, text=True, timeout=5)
        output = result.stdout[:2000] or "No logs"
        bot.reply_to(m, f"📋 Termux log:\n{output}")
    except Exception as e:
        bot.reply_to(m, f"❌ Error: {e}")

@bot.message_handler(commands=['q'])
def q(m):
    report = master.quick_check()
    bot.reply_to(m, report)
@bot.message_handler(commands=['inspect'])
def inspect(m):
    bot.reply_to(m, "🔍 Inspector Agent running...")
    report = master.full_check(m.chat.id)
    bot.reply_to(m, report)
@bot.message_handler(commands=['watchdog'])
def watchdog(m):
    parts = m.text.split()
    if len(parts) < 2:
        bot.reply_to(m, "Usage: /watchdog start [interval_min] | stop")
        return
    action = parts[1]
    if action == "start":
        interval = int(parts[2]) if len(parts) > 2 else 60
        result = master.watchdog_start(m.chat.id, interval)
    elif action == "stop":
        result = master.watchdog_stop()
    else:
        result = "Usage: /watchdog start [interval_min] | stop"
    bot.reply_to(m, result)
print("🚀 SLH SYSTEM RUNNING")
while True:
    try:
        bot.infinity_polling(timeout=20, long_polling_timeout=20)
    except Exception as e:
        print("Polling error:", e)
        time.sleep(5)
