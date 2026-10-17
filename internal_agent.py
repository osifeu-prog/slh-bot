import state_manager
import json, time, datetime, os, threading, traceback, uuid

ALLOWED = {"complete","whoami","dbsize","status","uptime","sysinfo","logs","errors","restart","ask"}

def run_command(cmd, msg):
    try:
        if cmd == "whoami":
            return os.popen("whoami").read().strip()
        elif cmd == "dbsize":
            db_path = state_manager.DB_FILE
            return f"db.json: {os.path.getsize(db_path)} bytes" if os.path.exists(db_path) else "db.json not found"
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

CLAIM_TTL_SECONDS = 10 * 60


def _claim_is_stale(record, now):
    if not isinstance(record, dict):
        return True
    try:
        claimed_at = datetime.datetime.fromisoformat(str(record.get("claimed_at") or ""))
        if claimed_at.tzinfo is None:
            claimed_at = claimed_at.replace(tzinfo=datetime.timezone.utc)
        return (now - claimed_at).total_seconds() >= CLAIM_TTL_SECONDS
    except (TypeError, ValueError, OverflowError):
        return True


def _claim_next_agent_message(agent_name=None, exclude_names=()):
    """Claim one inbox item atomically; never run a command while holding the DB lock."""
    now = datetime.datetime.now(datetime.timezone.utc)
    excluded = {str(name) for name in (exclude_names or ())}

    def eligible(name):
        name = str(name)
        return (agent_name is None or name == str(agent_name)) and name not in excluded

    # Avoid rewriting the canonical JSON on every idle polling interval.
    snapshot = state_manager.load_db()
    snapshot_agents = snapshot.get("agents", {})
    if not isinstance(snapshot_agents, dict):
        return None

    work_exists = False
    for name, data in snapshot_agents.items():
        if not eligible(name) or not isinstance(data, dict):
            continue
        inbox = data.get("inbox")
        processing = data.get("processing")
        if isinstance(inbox, list) and inbox:
            work_exists = True
            break
        if isinstance(processing, dict) and any(
            _claim_is_stale(record, now) for record in processing.values()
        ):
            work_exists = True
            break
    if not work_exists:
        return None

    claim_id = uuid.uuid4().hex
    claimed_at = now.isoformat()

    def mutate(db):
        agents = db.setdefault("agents", {})
        if not isinstance(agents, dict):
            return None

        # Recover abandoned claims after a worker crash. The external command is
        # always run outside atomic_update; the bounded lease avoids permanent
        # inbox loss without holding the DB lock during subprocess/network work.
        for name, data in agents.items():
            if not eligible(name) or not isinstance(data, dict):
                continue
            inbox = data.get("inbox")
            if not isinstance(inbox, list):
                inbox = []
                data["inbox"] = inbox
            processing = data.get("processing")
            if not isinstance(processing, dict):
                processing = {}
                data["processing"] = processing

            reclaimed = []
            for old_id, record in list(processing.items()):
                if not _claim_is_stale(record, now):
                    continue
                processing.pop(old_id, None)
                if isinstance(record, dict) and "message" in record:
                    reclaimed.append(record["message"])
            if reclaimed:
                data["inbox"] = reclaimed + inbox

        for name, data in agents.items():
            if not eligible(name) or not isinstance(data, dict):
                continue
            inbox = data.get("inbox")
            if not isinstance(inbox, list) or not inbox:
                continue
            raw_message = inbox.pop(0)
            processing = data.setdefault("processing", {})
            if not isinstance(processing, dict):
                processing = {}
                data["processing"] = processing
            processing[claim_id] = {
                "message": raw_message,
                "claimed_at": claimed_at,
            }
            message = dict(raw_message) if isinstance(raw_message, dict) else {
                "command": str(raw_message or "")
            }
            return {
                "agent_name": str(name),
                "claim_id": claim_id,
                "message": message,
            }
        return None

    return state_manager.atomic_update(mutate)


def _finish_agent_message(agent_name, claim_id, output):
    """Commit a command result without replacing unrelated agent state."""
    def mutate(db):
        agents = db.get("agents", {})
        data = agents.get(str(agent_name)) if isinstance(agents, dict) else None
        if not isinstance(data, dict):
            return False
        processing = data.get("processing")
        if not isinstance(processing, dict) or claim_id not in processing:
            return False
        processing.pop(claim_id, None)
        outbox = data.setdefault("outbox", [])
        if not isinstance(outbox, list):
            outbox = []
            data["outbox"] = outbox
        outbox.append(str(output)[:2500])
        if len(outbox) > 20:
            data["outbox"] = outbox[-20:]
        return True

    return state_manager.atomic_update(mutate)


def agent_worker():
    while True:
        try:
            # The tutor has a dedicated worker so it cannot race this command
            # dispatcher for the same inbox message.
            claim = _claim_next_agent_message(exclude_names={"tutor"})
            if claim:
                msg = claim["message"]
                cmd = str(msg.get("command") or "").strip().lower()
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                started = time.time()
                if cmd in ALLOWED:
                    result = run_command(cmd, msg)
                else:
                    result = f"❌ '{cmd}' not allowed"
                elapsed = time.time() - started
                output = f"[{now}] {cmd}\n>> {str(result)[:2000]}\n⏱️ {elapsed:.1f}s"
                _finish_agent_message(claim["agent_name"], claim["claim_id"], output)
        except Exception:
            os.makedirs("logs", exist_ok=True)
            with open("logs/agent.log", "a", encoding="utf-8") as f:
                f.write(
                    f"{datetime.datetime.now()} Agent worker error: "
                    f"{traceback.format_exc()}\n"
                )
            time.sleep(5)
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
    uid = str(uid or "").strip()
    task_id_text = str(task_id or "").strip()
    if not uid:
        return "Missing uid"
    if not task_id_text:
        return "❌ Task not found"

    def mutate(db):
        students = db.get("students", {})
        student = students.get(uid) if isinstance(students, dict) else None
        if not isinstance(student, dict):
            return "❌ Not registered", None

        courses = db.get("courses", {})
        course = courses.get("bitcoin_mastery", {}) if isinstance(courses, dict) else {}
        tasks = course.get("tasks", {}) if isinstance(course, dict) else {}
        task = tasks.get(task_id_text) if isinstance(tasks, dict) else None
        if not isinstance(task, dict):
            return "❌ Task not found", None

        completed = student.get("completed_tasks", [])
        if not isinstance(completed, list):
            completed = []
            student["completed_tasks"] = completed
        if any(str(existing_id) == task_id_text for existing_id in completed):
            return f"✅ Task {task_id_text} already completed", None

        validation = str(task.get("validation") or "")
        if validation.startswith("file_exists:"):
            path = os.path.expanduser(validation.split(":", 1)[1])
            if not os.path.exists(path):
                return f"❌ File {path} not found", None

        points = task.get("reward", 0)
        student["points"] = student.get("points", 0) + points
        completed.append(task_id_text)
        students[uid] = student
        return f"✅ Task {task_id_text} completed! +{points} points", None

    try:
        result, error = state_manager.atomic_update(mutate)
        if error:
            return error
        return result
    except Exception:
        return "❌ DB error"


# Tutor auto-reply. Claim/pop and result recording are atomic; Ollama runs outside the DB lock.
def tutor_worker():
    while True:
        try:
            claim = _claim_next_agent_message(agent_name="tutor")
            if claim:
                msg = claim["message"]
                prompt = str(msg.get("command") or msg.get("prompt") or "").strip()
                try:
                    if not prompt:
                        answer = "Tutor: empty message"
                    else:
                        import subprocess as sp
                        answer = sp.check_output(
                            ["ollama", "run", "phi3:mini", prompt],
                            text=True,
                            timeout=30,
                        )[:1000]
                except Exception:
                    answer = f"Tutor: received '{prompt[:300]}'. LLM offline, but I'm learning!"
                _finish_agent_message(
                    claim["agent_name"], claim["claim_id"], str(answer)[:1000]
                )
        except Exception:
            # Keep the legacy helper non-fatal; state writes use the canonical
            # state manager and failed claims can be recovered after their lease.
            pass
        time.sleep(5)


threading.Thread(target=tutor_worker, daemon=True, name="legacy-tutor-worker").start()
