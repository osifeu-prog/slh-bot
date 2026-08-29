import state_manager
import json, time, datetime, os, threading, traceback

ALLOWED = {"complete","whoami","dbsize","status","uptime","sysinfo","logs","errors","restart","ask"}

def run_command(cmd, msg):
    try:
        if cmd == "whoami":
            return os.popen("whoami").read().strip()
        elif cmd == "dbsize":
            return f"db.json: {os.path.getsize('db.json')} bytes" if os.path.exists("db.json") else "db.json not found"
        elif cmd == "status":
            if os.path.exists("runtime/bot.pid"):
                with open("runtime/bot.pid") as f: pid = f.read().strip()
                return f"Bot running (PID {pid})" if os.path.exists(f"/proc/{pid}") else f"Stale PID {pid}"
            return "No PID file"
        elif cmd == "uptime":
            return os.popen("uptime").read().strip()
        elif cmd == "sysinfo":
            disk = os.popen("df -h").read()[:500]
            mem = os.popen("free -m").read()[:500]
            return f"Disk:\n{disk}\nMemory:\n{mem}"
        elif cmd == "logs":
            return os.popen("tail -n 20 logs/bot.log").read() if os.path.exists("logs/bot.log") else "No logs"
        elif cmd == "errors":
            return os.popen("tail -n 20 logs/error.log").read() if os.path.exists("logs/error.log") else "No errors"
        elif cmd == "restart":
            os.system("bash start.sh &")
            return "Restart triggered"
        elif cmd == "ask":
            prompt = msg.get("prompt", "")
            if not prompt:
                return "Usage: /sendagent mytermux ask <question>"
            import subprocess as sp
            try:
                res = sp.check_output(["ollama", "run", "phi3:mini", "ענה בעברית, בפסקה קצרה: " + prompt], text=True, timeout=120)
                return res.strip()
            except sp.TimeoutExpired:
                return "❌ Timeout"
            except Exception as e:
                return f"Ollama error: {e}"
        elif cmd == "complete":
            task_id = msg.get("task_id", "")
            if not task_id:
                return "Usage: /sendagent mytermux complete <task_id>"
            uid = msg.get("uid", "")
            if not uid:
                return "Missing uid"
            return complete_task(uid, task_id)
        else:
            return f"Unknown: {cmd}"
    except Exception as e:
        return f"Error: {e}"

def agent_worker():
    while True:
        try:
            with open("db.json") as f:
                db = json.load(f)
            changed = False
            for name, data in db.get("agents", {}).items():
                inbox = data.get("inbox", [])
                if not inbox:
                    continue
                outbox = data.setdefault("outbox", [])
                for msg in inbox[:]:
                    cmd = msg.get("command", "").strip().lower()
                    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    _start = time.time()
                    if cmd in ALLOWED:
                        res = run_command(cmd, msg)
                    else:
                        res = f"❌ '{cmd}' not allowed"
                    elapsed = time.time() - _start
                    outbox.append(f"[{now}] {cmd}\n>> {res[:2000]}\n⏱️ {elapsed:.1f}s")
                    inbox.remove(msg)
                    changed = True
                if len(outbox) > 20:
                    data["outbox"] = outbox[-20:]
            if changed:
                with open("db.json", "w") as f:
                    json.dump(db, f, indent=2, ensure_ascii=False)
        except Exception as e:
            # תיעוד שגיאה
            os.makedirs("logs", exist_ok=True)
            with open("logs/agent.log", "a") as f:
                f.write(f"{datetime.datetime.now()} Agent worker error: {traceback.format_exc()}\n")
            time.sleep(5)  # המתן לפני ניסיון חוזר
        time.sleep(2)

def start_agent_thread():
    try:
        t = threading.Thread(target=agent_worker, daemon=True, name="agent_worker")
        t.start()
        print("Internal agent thread started")
    except Exception as e:
        os.makedirs("logs", exist_ok=True)
        with open("logs/agent.log", "a") as f:
            f.write(f"{datetime.datetime.now()} Failed to start agent: {traceback.format_exc()}\n")
        print(f"Agent start error: {e}")
def complete_task(uid, task_id):
    try:
        with open("db.json") as f: db = json.load(f)
    except: return "❌ DB error"
    student = db.get("students", {}).get(uid)
    if not student: return "❌ Not registered"
    tasks = db.get("courses", {}).get("bitcoin_mastery", {}).get("tasks", {})
    task = tasks.get(str(task_id))
    if not task: return "❌ Task not found"
    # בדיקה: file_exists
    if task.get("validation", "").startswith("file_exists:"):
        path = os.path.expanduser(task["validation"].split(":",1)[1])
        if not os.path.exists(path):
            return f"❌ File {path} not found"
    # תגמול
    points = task.get("reward", 0)
    student.setdefault("points", 0)
    student["points"] += points
    # שמירת השלמה
    completed = student.setdefault("completed_tasks", [])
    if task_id not in completed:
        completed.append(task_id)
    db["students"][uid] = student
    with open("db.json","w") as f: json.dump(db, f, indent=2, ensure_ascii=False)
    return f"✅ Task {task_id} completed! +{points} points"

# Tutor auto-reply
def tutor_worker():
    import time, json
    while True:
        try:
            agents = state_manager.get_agents()
            tutor = agents.get("tutor", {})
            inbox = tutor.get("inbox", [])
            if inbox:
                msg = inbox.pop(0)["command"]
                # try Ollama
                try:
                    import subprocess as sp
                    ans = sp.check_output(["ollama", "run", "phi3:mini", msg], text=True, timeout=30)[:1000]
                except:
                    ans = f"Tutor: received '{msg}'. LLM offline, but I'm learning!"
                tutor.setdefault("outbox", []).append(ans)
                agents["tutor"] = tutor
                state_manager.set_agents(agents)
        except:
            pass
        time.sleep(5)

threading.Thread(target=tutor_worker, daemon=True).start()
