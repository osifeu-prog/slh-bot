"""Internal agent workers using canonical, atomic SLH state updates.

Inbox messages are claimed under the DB lock, processed without holding it, and
finalized atomically. Claims have a lease so a worker crash does not permanently
strand a message. Commands with financial/task side effects must be idempotent.
"""
import datetime
import os
import threading
import time
import traceback
import uuid
from pathlib import Path

import state_manager

ALLOWED = {"complete", "whoami", "dbsize", "status", "uptime", "sysinfo", "logs", "errors", "restart", "ask"}
CLAIM_LEASE_SECONDS = 600
MAX_OUTBOX = 20
MAX_OUTPUT = 2000
_TUTOR_THREAD_STARTED = False
_AGENT_THREAD_STARTED = False
_WORKER_START_LOCK = threading.Lock()


def run_command(cmd, msg):
    try:
        if cmd == "whoami":
            return os.popen("whoami").read().strip()
        elif cmd == "dbsize":
            path = Path(getattr(state_manager, "DB_FILE", "state/db.json"))
            return f"db.json: {path.stat().st_size} bytes" if path.exists() else "db.json not found"
        elif cmd == "status":
            if os.path.exists("runtime/bot.pid"):
                with open("runtime/bot.pid", encoding="utf-8") as f:
                    pid = f.read().strip()
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
                res = sp.check_output(
                    ["ollama", "run", "phi3:mini", "ענה בעברית, בפסקה קצרה: " + prompt],
                    text=True,
                    timeout=120,
                )
                return res.strip()
            except sp.TimeoutExpired:
                return "❌ Timeout"
            except Exception as exc:
                return f"Ollama error: {exc}"
        elif cmd == "complete":
            task_id = msg.get("task_id", "")
            if not task_id:
                return "Usage: /sendagent mytermux complete <task_id>"
            uid = msg.get("uid", "")
            if not uid:
                return "Missing uid"
            return complete_task(uid, task_id)
        return f"Unknown: {cmd}"
    except Exception as exc:
        return f"Error: {exc}"


def _claim_inbox(agent_filter=None, *, exclude_agents=(), max_messages=1):
    """Claim at most max_messages under one atomic update to keep leases bounded."""
    now = time.time()
    claimed = []
    limit = max(1, int(max_messages))

    def mutate(db):
        agents = db.setdefault("agents", {})
        if not isinstance(agents, dict):
            raise ValueError("agents must be an object")
        for name, data in agents.items():
            if len(claimed) >= limit:
                break
            if not isinstance(data, dict):
                continue
            if agent_filter is not None and name not in agent_filter:
                continue
            if name in exclude_agents:
                continue
            inbox = data.setdefault("inbox", [])
            processing = data.setdefault("processing", [])
            if not isinstance(inbox, list) or not isinstance(processing, list):
                raise ValueError(f"invalid inbox/processing for agent {name}")

            # Requeue expired claims. Keep the original message data intact.
            still_processing = []
            for entry in processing:
                if not isinstance(entry, dict) or not isinstance(entry.get("message"), dict):
                    continue
                try:
                    expired = now - float(entry.get("claimed_at", now)) >= CLAIM_LEASE_SECONDS
                except (TypeError, ValueError):
                    expired = True
                if expired:
                    inbox.append(entry["message"])
                else:
                    still_processing.append(entry)
            data["processing"] = still_processing

            while inbox and len(claimed) < limit:
                msg = inbox.pop(0)
                if not isinstance(msg, dict):
                    msg = {"command": str(msg)}
                claim_id = uuid.uuid4().hex
                data["processing"].append({
                    "claim_id": claim_id,
                    "message": msg,
                    "claimed_at": now,
                })
                claimed.append((str(name), claim_id, dict(msg)))
    state_manager.atomic_update(mutate)
    return claimed


def _finalize_message(agent_name, claim_id, output):
    """Commit output and remove a claim atomically; never save a stale DB snapshot."""
    result = {"finalized": False}

    def mutate(db):
        agents = db.get("agents", {})
        agent = agents.get(agent_name) if isinstance(agents, dict) else None
        if not isinstance(agent, dict):
            return
        processing = agent.setdefault("processing", [])
        match = next(
            (entry for entry in processing
             if isinstance(entry, dict) and entry.get("claim_id") == claim_id),
            None,
        )
        if match is None:
            return
        processing.remove(match)
        outbox = agent.setdefault("outbox", [])
        if not isinstance(outbox, list):
            raise ValueError(f"invalid outbox for agent {agent_name}")
        outbox.append(output[:MAX_OUTPUT])
        del outbox[:-MAX_OUTBOX]
        result["finalized"] = True

    state_manager.atomic_update(mutate)
    return result["finalized"]


def _log_worker_error(label):
    os.makedirs("logs", exist_ok=True)
    with open("logs/agent.log", "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now()} {label}: {traceback.format_exc()}\n")


def agent_worker():
    while True:
        try:
            claimed = _claim_inbox(exclude_agents={"tutor"})
            for name, claim_id, msg in claimed:
                cmd = str(msg.get("command", "")).strip().lower()
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                started = time.time()
                res = run_command(cmd, msg) if cmd in ALLOWED else f"❌ '{cmd}' not allowed"
                elapsed = time.time() - started
                output = f"[{now}] {cmd}\n>> {str(res)[:MAX_OUTPUT]}\n⏱️ {elapsed:.1f}s"
                _finalize_message(name, claim_id, output)
        except Exception:
            _log_worker_error("Agent worker error")
            time.sleep(5)
        time.sleep(2)


def tutor_worker():
    while True:
        try:
            claimed = _claim_inbox(agent_filter={"tutor"})
            for name, claim_id, msg in claimed:
                command = str(msg.get("command", ""))
                try:
                    import subprocess as sp
                    ans = sp.check_output(
                        ["ollama", "run", "phi3:mini", command],
                        text=True,
                        timeout=30,
                    )[:1000]
                except Exception:
                    ans = f"Tutor: received '{command}'. LLM offline, but I'm learning!"
                _finalize_message(name, claim_id, ans)
        except Exception:
            _log_worker_error("Tutor worker error")
        time.sleep(5)


def start_agent_thread():
    """Start background workers once when requested by the live runtime."""
    global _TUTOR_THREAD_STARTED, _AGENT_THREAD_STARTED
    try:
        with _WORKER_START_LOCK:
            if not _AGENT_THREAD_STARTED:
                threading.Thread(target=agent_worker, daemon=True, name="agent_worker").start()
                _AGENT_THREAD_STARTED = True
            if not _TUTOR_THREAD_STARTED:
                threading.Thread(target=tutor_worker, daemon=True, name="tutor_worker").start()
                _TUTOR_THREAD_STARTED = True
        print("Internal agent threads started")
    except Exception as exc:
        _log_worker_error("Failed to start agent")
        print(f"Agent start error: {exc}")


def complete_task(uid, task_id):
    """Complete a course task once, awarding its points in the canonical DB."""
    uid = str(uid)
    task_key = str(task_id)

    try:
        snapshot = state_manager.load_db()
    except Exception:
        return "❌ DB error"

    student = snapshot.get("students", {}).get(uid)
    if not isinstance(student, dict):
        return "❌ Not registered"
    tasks = snapshot.get("courses", {}).get("bitcoin_mastery", {}).get("tasks", {})
    task = tasks.get(task_key) if isinstance(tasks, dict) else None
    if not isinstance(task, dict):
        return "❌ Task not found"

    validation = str(task.get("validation", ""))
    if validation.startswith("file_exists:"):
        path = os.path.expanduser(validation.split(":", 1)[1])
        if not os.path.exists(path):
            return f"❌ File {path} not found"

    result = {"message": "❌ Task could not be completed"}

    def mutate(db):
        students = db.get("students", {})
        current_student = students.get(uid) if isinstance(students, dict) else None
        current_tasks = db.get("courses", {}).get("bitcoin_mastery", {}).get("tasks", {})
        current_task = current_tasks.get(task_key) if isinstance(current_tasks, dict) else None
        if not isinstance(current_student, dict):
            result["message"] = "❌ Not registered"
            return
        if not isinstance(current_task, dict):
            result["message"] = "❌ Task not found"
            return
        if str(current_task.get("validation", "")) != validation:
            result["message"] = "❌ Task changed; retry completion"
            return

        completed = current_student.setdefault("completed_tasks", [])
        if not isinstance(completed, list):
            result["message"] = "❌ Invalid completion record"
            return
        if any(str(done) == task_key for done in completed):
            result["message"] = f"ℹ️ Task {task_key} already completed; no extra points awarded."
            return

        points = current_task.get("reward", 0)
        if isinstance(points, bool) or not isinstance(points, (int, float)):
            result["message"] = "❌ Invalid task reward"
            return
        old_points = current_student.get("points", 0)
        if isinstance(old_points, bool) or not isinstance(old_points, (int, float)):
            result["message"] = "❌ Invalid student points"
            return
        current_student["points"] = old_points + points
        completed.append(task_key)
        result["message"] = f"✅ Task {task_key} completed! +{points} points"

    try:
        state_manager.atomic_update(mutate)
    except Exception:
        return "❌ DB error"
    return result["message"]

def _maybe_start_workers():
    """Start the internal workers only when the bot runtime is explicitly enabled."""
    if os.getenv("RUN_BOT", "").strip() == "1":
        start_agent_thread()


# Production entrypoint loads this module via complete_handler. Keep ordinary imports
# side-effect-free in tests/tools, but restore worker startup in the active bot runtime.
_maybe_start_workers()
