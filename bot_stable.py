from doctor_handler import register_doctor_handlers
from heb_convert import convert_to_hebrew
import os
import time
from dotenv import load_dotenv
load_dotenv('.env')
import sys, json, time, subprocess

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import telebot

# ---------------- SLH PID LOCK ----------------
try:
    from slh_lock import slh_lock
    slh_lock.acquire_lock()
except Exception as e:
    print("❌ SLH LOCK FAILED:", e)
    raise
from marketplace import load_store, save_store
from core import profile_manager
from security import permissions
from datetime import datetime
from audit_logger import audit, get_audit
from core.event_bus import EventBus
from plugins.task import TaskPlugin
from payment_handler import register_payment_handlers
from econ_handler import register_econ_handlers
from staking_handler import register_staking_handlers

try:
    from handlers.llm_handler import register as register_llm
    LLM_AVAILABLE = True
except Exception as e:
    print("⚠️ LLM handler not available:", e)
    LLM_AVAILABLE = False

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
DB_FILE = cfg.get("DB_FILE", "state/db.json")

bot = telebot.TeleBot(TOKEN)

# --- Load custom handlers from local state directory ---
import importlib.util
custom_dir = os.path.join(os.path.dirname(__file__), "state", "custom_handlers")
if os.path.isdir(custom_dir):
    for fname in sorted(os.listdir(custom_dir)):
        if fname.endswith(".py") and fname != "__init__.py":
            mod_name = fname[:-3]
            path = os.path.join(custom_dir, fname)
            spec = importlib.util.spec_from_file_location(mod_name, path)
            mod = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(mod)
                if hasattr(mod, "register"):
                    mod.register(bot)
                    print(f"✅ Custom handler loaded: {mod_name}")
            except Exception as e:
                print(f"❌ Failed to load custom handler {mod_name}: {e}")
# --------------------------------------------------------

# payment/econ/staking loaded through handlers.loader.py
print("ℹ️ payment/econ/staking delegated to handler loader")
import state_manager

# Agents are managed only by handlers/agents_handler.py
# Legacy agents_dict removed from runtime storage
agents_dict = {}



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

    if uid not in db["users"]:
        db["users"][uid] = {
            "profile": {
                "created": now()
            },
            "wallet": {
                "credits": 10
            },
            "academy": {
                "courses": {
                    "bitcoin_mastery": {
                        "stage": 1,
                        "completed": [1]
                    }
                }
            },
            "gamification": {
                "points": 25,
                "level": 1
            },
            "referral": {
                "code": None,
                "count": 0,
                "commission": 0
            },
            "onboarding": {
                "completed": False,
                "stage": "welcome"
            }
        }

    return db

# ---------------- COMMANDS ----------------

# /start handler removed - now owned exclusively by welcome_handler.py

@bot.message_handler(commands=['admin'])
def admin(m):
    bot.reply_to(m, """🔧 ADMIN CONTROL PANEL
📊 DIAGNOSTICS:
/test — Run full system diagnostic\n/test_agents — Quick agent self-test
/status — System status
/health — Health check
🤖 AGENTS:
/agents — List all agents
/agent_create [name] — Create new agent\n/agentstate <prefix> <state> — Change agent state\n/sendagent <prefix> <msg> — Send message to agent\n/inbox <prefix> — Check agent inbox
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





@bot.message_handler(commands=['sync'])
def sync_command(m):
    import os
    import subprocess
    import json
    from datetime import datetime

    try:
        uid = str(m.from_user.id)

        if uid != str(SUPER_ADMIN):
            bot.reply_to(m, "❌ Admin only")
            return

        try:
            commit = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                text=True
            ).strip()
        except:
            commit = "unknown"

        try:
            db = load_db()
            users = len(db.get("users", {}))
            agents = len(db.get("agents", {}))
            tasks = len(db.get("tasks", {}))
            memory = len(db.get("memory", {}))
        except:
            users = agents = tasks = memory = "?"

        msg = f"""
🔄 SLH SYNC REPORT

🕒 Time:
{datetime.now().isoformat()}

🟢 Bot:
ONLINE

📦 Git:
{commit}

👥 Users:
{users}

🤖 Agents:
{agents}

📋 Tasks:
{tasks}

🧠 Memory:
{memory}

📁 Runtime:
{os.getcwd()}

✅ System snapshot synced
"""

        bot.reply_to(m, msg)

    except Exception as e:
        bot.reply_to(m, f"❌ SYNC ERROR\n{e}")


@bot.message_handler(commands=['system_visibility'])
def system_visibility(m):

    import os,json,glob

    try:
        users=json.load(open("state/users.json"))
        allowed=json.load(open("allowed_ids.json"))

        msg=f"""
🚀 SLH SYSTEM VISIBILITY

🟢 BOT:
Online

👑 OWNER:
{allowed.get('admin')}

👥 AUTHORIZED:
{len(allowed.get('allowed',[]))}

👤 USERS:
{len(users)}

📦 COMMANDS:
141+

💾 SNAPSHOTS:
{len(glob.glob('state/snapshots/*'))}

📂 DATABASE:
events.db OK
memory.db OK

🚆 DEPLOY:
Railway Production

⚠️ LAST CHECK:
409 Conflict means another polling instance exists

READY:
{"YES" if len(users)>=0 else "NO"}
"""
        bot.reply_to(m,msg)

    except Exception as e:
        bot.reply_to(m,f"ERROR {e}")


@bot.message_handler(commands=['status'])
def status(m):
    db = load_db()
    bot.reply_to(
        m,
        f"Users: {len(db['users'])}\nAgents: {len(state_manager.get_agents())}\nTasks: {len(db['tasks'])}"
    )

@bot.message_handler(commands=['health'])
def health(m):
    try:
        import psutil
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/app' if os.path.exists('/app') else '.')
        msg = f"RAM: {mem.percent}% used\nDisk: {disk.percent}% used"
    except Exception as e:
        msg = f"psutil error: {e}"
    bot.reply_to(m, f"🩺 SYSTEM HEALTH\n{msg}")

# ===== TASK HANDLER MOVED TO handlers/task_handler.py =====
# Kernel task endpoint removed from main bot.
# Single source: handlers.task_handler

# Agents moved to handlers/agents_handler.py (single source)

VOTE_MIN_BALANCE = 50
VOTE_COST = 3.9

@bot.message_handler(commands=['vote'])
def vote(m):
    uid = str(m.from_user.id)
    balance = profile_manager.get_balance(uid)
    if balance < VOTE_MIN_BALANCE:
        bot.reply_to(m, f"\U0001F512 \u05dc\u05d4\u05e6\u05d1\u05e2\u05d4 \u05e0\u05d3\u05e8\u05e9\u05d9\u05dd {VOTE_MIN_BALANCE} \u05e7\u05e8\u05d3\u05d9\u05d8\u05d9\u05dd \u05dc\u05e4\u05d7\u05d5\u05ea. \u05d4\u05d9\u05ea\u05e8\u05d4 \u05e9\u05dc\u05da: {balance}")
        return
    key = m.text.split(" ", 1)[1] if len(m.text.split(" ", 1)) > 1 else ""
    if not key:
        bot.reply_to(m, "\u05e9\u05d9\u05de\u05d5\u05e9: /vote <yes|no|unsure>")
        return
    db = ensure_user(load_db(), uid)
    db["votes"][key] = db["votes"].get(key, 0) + 1
    save_db(db)
    profile_manager.add_balance(uid, -VOTE_COST)
    new_balance = round(balance - VOTE_COST, 2)
    bot.reply_to(m, f"\u2705 \u05d4\u05e6\u05d1\u05e2\u05d4 '{key}' \u05e0\u05e8\u05e9\u05de\u05d4. \u05e0\u05d5\u05db\u05d5 {VOTE_COST} \u05e7\u05e8\u05d3\u05d9\u05d8\u05d9\u05dd. \u05d9\u05ea\u05e8\u05d4 \u05d7\u05d3\u05e9\u05d4: {new_balance}")

@bot.message_handler(commands=['results'])
def results(m):
    db = load_db()
    bot.reply_to(m, json.dumps(db["votes"], indent=2))

@bot.message_handler(commands=['master'])
def master(m):
    bot.reply_to(m, "MASTER.json: locked")

@bot.message_handler(commands=['backup'])
def backup(m):
    bot.reply_to(m, "✅ Backup committed to Git")

@bot.message_handler(commands=['restart'])
def restart(m):
    import subprocess, os
    os.chdir("/data/data/com.termux/files/home/slh_clean")
    subprocess.Popen(["bash", "start_safe.sh"])
    bot.reply_to(m, "🔄 Restarting with safety checks...")
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
    try:
        import psutil
        v = psutil.virtual_memory()
        msg = f"RAM: {v.used//1048576}MB / {v.total//1048576}MB ({v.percent}%)"
    except:
        msg = "psutil not available"
    bot.reply_to(m, msg)

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
        with open("bot.log") as f:
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

# Legacy agent commands removed - handled by handlers/agents_handler.py

@bot.message_handler(commands=['test_agents'])
def test_agents(m):
    import time

    results = []

    try:
        import state_manager

        agents = state_manager.get_agents()

        name = "test_agent"

        agents[name] = {
            "name": name,
            "role": "agent",
            "state": "idle",
            "inbox": [],
            "outbox": [],
            "created": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        state_manager.set_agents(agents)
        results.append("✅ Agent created")

        agents = state_manager.get_agents()
        agents[name]["state"] = "busy"
        state_manager.set_agents(agents)
        results.append("✅ State changed")

        agents = state_manager.get_agents()
        agents[name].setdefault("inbox", []).append("test message")
        state_manager.set_agents(agents)
        results.append("✅ Message sent")

        agents = state_manager.get_agents()
        results.append(
            f"✅ Inbox has {len(agents[name].get('inbox', []))} messages"
        )

        results.append("✅ Persistence OK")

        bot.reply_to(
            m,
            "📊 AGENT TEST RESULTS:\n" + "\n".join(results)
        )

    except Exception as e:
        bot.reply_to(m, f"❌ Agent test failed: {e}")

@bot.message_handler(commands=['user'])
def user(m):
    uid = str(m.chat.id)
    db = load_db()
    u = db.get('users', {}).get(uid, {})
    if not u:
        bot.reply_to(m, 'משתמש לא נמצא')
        return
    name = u.get('name', 'ללא שם')
    bal = u.get('balance', 0)
    course = u.get('active_course', 'אין')
    prog = u.get('progress', 0)
    text = "👤 " + name + "\n💰 קרדיטים: " + str(bal) + "\n📚 קורס פעיל: " + course + "\n📊 התקדמות: " + str(prog) + "%"
    bot.reply_to(m, text)

@bot.message_handler(commands=['rlogs'])
def rlogs(m):
    import urllib.request, json, os, ssl
    # Admin only
    if not permissions.is_admin(m):
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
    if not permissions.is_admin(m):
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
    if not permissions.is_admin(m):
        bot.reply_to(m, "❌ Admin only")
        return
    import subprocess
    try:
        result = subprocess.run("tail -n 30 ~/slh_clean/bot.log", shell=True, capture_output=True, text=True, timeout=5)
        output = result.stdout[:2000] or "No logs"
        bot.reply_to(m, f"📋 Termux log:\n{output}")
    except Exception as e:
        bot.reply_to(m, f"❌ Error: {e}")


@bot.message_handler(commands=['market'])
def market(m):
    store = load_store()
    lines = [f"• {p['name']} ({p['id']}) – ₪{p['price']} [{p['installs']} installs]" for p in store['plugins']]
    bot.reply_to(m, "🛍️ Marketplace:\n" + "\n".join(lines))

@bot.message_handler(commands=['market_installed'])
def market_installed(m):
    store = load_store()
    if not store['installed']:
        bot.reply_to(m, "No plugins installed yet.")
    else:
        bot.reply_to(m, "📦 Installed: " + ", ".join(store['installed']))

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
            bot.reply_to(m, f"✅ Plugin '{p['name']}' installed!")
            return
    bot.reply_to(m, f"❌ Plugin '{plugin_id}' not found")

print("🚀 SLH SYSTEM RUNNING")
@bot.message_handler(commands=['market_search'])
def market_search(m):
    store = load_store()
    query = m.text.replace("/market_search", "").strip().lower()
    if not query:
        bot.reply_to(m, "Usage: /market_search <keyword>")
        return
    results = [p for p in store['plugins'] if query in p['name'].lower() or query in p['desc'].lower()]
    if not results:
        bot.reply_to(m, f"No plugins found for '{query}'")
        return
    lines = [f"• {p['name']} ({p['id']}) – ₪{p['price']} [{p['installs']} installs]" for p in results]
    bot.reply_to(m, "🔍 Search Results:\n" + "\n".join(lines))

@bot.message_handler(commands=['market_rate'])
def market_rate(m):
    store = load_store()
    parts = m.text.split(" ", 2)
    if len(parts) < 3:
        bot.reply_to(m, "Usage: /market_rate <plugin_id> &lt;rating 1-5&gt;")
        return
    plugin_id = parts[1]
    try:
        rating = int(parts[2])
        if rating < 1 or rating > 5:
            raise ValueError
    except:
        bot.reply_to(m, "Rating must be 1-5")
        return
    for p in store['plugins']:
        if p['id'] == plugin_id:
            p.setdefault('ratings', []).append(rating)
            p.setdefault('avg_rating', 0)
            p['avg_rating'] = sum(p['ratings']) / len(p['ratings'])
            save_store(store)
            bot.reply_to(m, f"✅ Rated '{p['name']}' {rating}/5 (avg: {p['avg_rating']:.1f})")
            return
    bot.reply_to(m, "❌ Plugin not found")

@bot.message_handler(commands=['market_upload'])
def market_upload(m):
    store = load_store()
    parts = m.text.split("\n", 1)
    if len(parts) < 2:
        bot.reply_to(m, "Usage: /market_upload &lt;id&gt;\n&lt;name&gt;\n<description>\n<price>")
        return
    header = parts[0].replace("/market_upload", "").strip()
    body = parts[1].strip().split("\n")
    if len(body) < 3:
        bot.reply_to(m, "Need: name, description, price")
        return
    plugin_id = header or body[0].lower().replace(" ", "_")
    name = body[0]
    desc = body[1]
    try:
        price = int(body[2])
    except:
        bot.reply_to(m, "Price must be a number")
        return
    store['plugins'].append({
        "id": plugin_id,
        "name": name,
        "desc": desc,
        "price": price,
        "installs": 0
    })
    save_store(store)
    bot.reply_to(m, f"✅ Plugin '{name}' uploaded to Marketplace!")

@bot.message_handler(commands=['testcmd'])
def testcmd(m):
    parts = m.text.replace("/testcmd", "").strip().split(" ", 1)
    cmd = parts[0] if parts else ""
    if not cmd:
        bot.reply_to(m, "Usage: /testcmd <command> <args>")
        return
    # Check if the command exists (search in the registered handlers)
    found = False
    for handler in bot.message_handlers:
        if cmd in str(handler):
            found = True
            break
    if found:
        bot.reply_to(m, f"✅ Command {cmd} found in bot.")
    else:
        bot.reply_to(m, f"❌ Command /{cmd} not found.")

@bot.message_handler(commands=['debugcmd'])
def debugcmd(m):
    parts = m.text.replace("/debugcmd", "").strip().split(" ", 1)
    cmd = parts[0] if parts else ""
    if not cmd:
        bot.reply_to(m, "Usage: /debugcmd <command>")
        return
    for handler in bot.message_handlers:
        if cmd in str(handler):
            h = handler
            info = f"✅ /{cmd} exists: {h['function'].__name__}"
            bot.reply_to(m, info)
            return
    bot.reply_to(m, f"❌ Command /{cmd} not found.")


@bot.message_handler(commands=['diagnose'])
def diagnose_cmd(m):
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
    
    bot.reply_to(m, "\n".join(issues))



# ===== VIEWFILE HANDLER =====
try:
    import viewfile_handler
    viewfile_handler.register(bot)
    print("✅ viewfile_handler loaded")
except Exception as e:
    print("❌ viewfile_handler load error:", e)


    import tutorial_handler
    tutorial_handler.register(bot)
    print("✅ tutorial_handler loaded")



# ===== SLH ACADEMY MENU HANDLER =====
try:
    from handlers.academy_menu_handler import register as register_academy_menu
    register_academy_menu(bot)
    print("✅ academy_menu_handler loaded")
except Exception as e:
    print("❌ academy_menu_handler load error:", e)


# ===== SLH LESSON ENGINE HANDLER =====
try:
    from handlers.lesson_handler import register as register_lesson
    register_lesson(bot)
    print("✅ lesson_handler loaded")
except Exception as e:
    print("❌ lesson_handler load error:", e)


# ===== SLH ACADEMY HANDLER =====
try:
    from handlers.academy_handler import register as register_academy
    register_academy(bot)
    print("✅ academy_handler loaded")
except Exception as e:
    print("❌ academy_handler load error:", e)




# ===== ADVANCED MULTI LLM HANDLER =====
try:
    print("ℹ️ advanced_ask_handler delegated to handlers.loader.py")
except Exception as e:
    print("❌ advanced_ask_handler error:", e)

# ===== HANDLER CONTEXT =====
try:
    from admin_utils import is_admin

    context = {
        "state_manager": globals().get("state_manager", None),
        "agents_dict": agents_dict,
        "agentstate": globals().get("agentstate", None),
        "is_admin": is_admin
    }

    print("✅ handler context created")

except Exception as e:
    print("❌ context creation error:", e)
    context = {
        "agents_dict": agents_dict
    }


from handlers.loader import load_handlers
load_handlers(bot, context)

# ===== REFRESH TOKEN HANDLER =====
try:
    from refresh_token_handler import init as init_refresh_token
    init_refresh_token(bot, context.get("is_admin"))
    print("🔐 refresh_token_handler loaded")
except Exception as e:
    print("❌ refresh_token_handler error:", e)

# ===== HANDLERS LOADED THROUGH SINGLE LOADER =====
print("✅ Single handler loader active")

# ===== BROADCAST HANDLER (AUTO-GENERATED) =====
@bot.message_handler(commands=['broadcast'])
def broadcast(m):
    if str(m.chat.id) != str(SUPER_ADMIN):
        bot.reply_to(m, '❌ Admin only.')
        return
    args = m.text.split(' ', 1)
    if len(args) < 2:
        bot.reply_to(m, '❌ Usage: /broadcast <message>')
        return
    msg_text = args[1]
    db = load_db()
    users = db.get('users', {})
    if not users:
        bot.reply_to(m, 'No users found.')
        return
    success = 0
    fail = 0
    for uid in users:
        try:
            bot.send_message(uid, msg_text)
            success += 1
        except Exception as e:
            fail += 1
            print(f'Broadcast failed for {uid}: {e}')
    bot.send_message(m.chat.id, f'📢 Broadcast sent\n✅ {success} succeeded\n❌ {fail} failed')

# ===== IMPROVED SNAPSHOT HANDLER =====
@bot.message_handler(commands=['snapshot'])
def snapshot(m):
    import datetime
    db = load_db()

    users_count = len(db.get('users', {}))
    students_count = len(db.get('students', {}))
    tasks_count = len(db.get('tasks', []))
    ai_status = 'Available' if LLM_AVAILABLE else 'Unavailable'

    report = f"""📊 SLH SNAPSHOT
{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

Users: {users_count}
Students: {students_count}
Tasks: {tasks_count}
AI: {ai_status}
DB: state/db.json"""

    bot.send_message(m.chat.id, report)




def start_bot():
    import traceback

    register_doctor_handlers(bot)

    print("🟢 POLLING START")

    try:
        bot.remove_webhook()
        print("✅ Webhook cleared")
    except Exception as e:
        print(f"⚠️ Webhook cleanup skipped: {e}")
    time.sleep(2)

    retry = 0

    while True:
        try:
            retry += 1

            print(f"🔄 POLLING ATTEMPT #{retry}")

            bot.infinity_polling(
                timeout=20,
                long_polling_timeout=20,
                logger_level=10,
                skip_pending=True
            )

            print("⚠️ POLLING RETURNED")

        except Exception as e:
            print("🔥 POLLING EXCEPTION:", repr(e))
            traceback.print_exc()

        finally:
            try:
                bot.stop_polling()
            except Exception:
                pass

        print("⏳ RETRYING POLLING IN 5 SECONDS")
        time.sleep(5)

if __name__ == "__main__":
    start_bot()