import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

DB_PATH = Path("state/db.json")
WORK_LOG_PATH = Path("state/work_log.json")
TZ = ZoneInfo("Asia/Jerusalem")


def _now():
    return datetime.now(TZ)


def _iso(dt=None):
    return (dt or _now()).isoformat()


def _parse(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def _load_db():
    return json.loads(DB_PATH.read_text(encoding="utf-8"))


def get_progress():
    db = _load_db()
    tasks = db.get("tasks", {})
    return [
        (task.get("title", task_id), task.get("progress", 0))
        for task_id, task in tasks.items()
    ]


def _load_work_log():
    if not WORK_LOG_PATH.exists():
        return []
    try:
        data = json.loads(WORK_LOG_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_work_log(log):
    WORK_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        prefix=".work_log.",
        suffix=".tmp",
        dir=str(WORK_LOG_PATH.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(log, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, WORK_LOG_PATH)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def _active_entry(log, task_name, user_id):
    uid = str(user_id)
    for entry in reversed(log):
        if (
            entry.get("task") == task_name
            and str(entry.get("user")) == uid
            and entry.get("stop") is None
            and entry.get("status", "running") in {"running", "paused"}
        ):
            return entry
    return None


def _seconds_between(start, end):
    if not start or not end:
        return 0.0
    delta = (end - start).total_seconds()
    return max(0.0, delta)


def _refresh_derived(entry, now=None):
    now = now or _now()
    start = _parse(entry.get("start"))
    if not start:
        return entry

    pause_started = _parse(entry.get("pause_started"))
    stop = _parse(entry.get("stop"))
    end = stop or now

    wall = _seconds_between(start, end)
    paused = float(entry.get("paused_seconds", 0) or 0)
    if pause_started and entry.get("status") == "paused":
        paused += _seconds_between(pause_started, now)

    entry["wall_seconds"] = round(wall, 3)
    entry["active_seconds"] = round(max(0.0, wall - paused), 3)
    entry["paused_seconds"] = round(max(0.0, paused), 3)
    return entry


def start_work(task_name, user_id, task_id=None, phase=None):
    task_name = str(task_name or "").strip()
    if not task_name:
        return False

    log = _load_work_log()
    # Keep one active clock per user so task-less pause/resume/stop stays deterministic.
    uid = str(user_id)
    for existing in reversed(log):
        if (
            str(existing.get("user")) == uid
            and existing.get("stop") is None
            and existing.get("status", "running") in {"running", "paused"}
        ):
            return False

    now = _now()
    entry = {
        "task": task_name,
        "task_id": task_id,
        "user": str(user_id),
        "start": _iso(now),
        "stop": None,
        "status": "running",
        "phase": phase,
        "pause_started": None,
        "paused_seconds": 0.0,
        "wall_seconds": 0.0,
        "active_seconds": 0.0,
        "version": 2,
    }
    log.append(entry)
    _save_work_log(log)
    return True


def pause_work(task_name, user_id):
    log = _load_work_log()
    entry = _active_entry(log, task_name, user_id)
    if not entry:
        return False
    if entry.get("status") == "paused":
        return True

    entry["status"] = "paused"
    entry["pause_started"] = _iso()
    _refresh_derived(entry)
    _save_work_log(log)
    return True


def resume_work(task_name, user_id):
    log = _load_work_log()
    entry = _active_entry(log, task_name, user_id)
    if not entry:
        return False
    if entry.get("status") != "paused":
        return True

    now = _now()
    pause_started = _parse(entry.get("pause_started"))
    if pause_started:
        entry["paused_seconds"] = round(
            float(entry.get("paused_seconds", 0) or 0)
            + _seconds_between(pause_started, now),
            3,
        )
    entry["pause_started"] = None
    entry["status"] = "running"
    _refresh_derived(entry, now)
    _save_work_log(log)
    return True


def stop_work(task_name, user_id):
    log = _load_work_log()
    entry = _active_entry(log, task_name, user_id)
    if not entry:
        return False

    now = _now()
    if entry.get("status") == "paused":
        pause_started = _parse(entry.get("pause_started"))
        if pause_started:
            entry["paused_seconds"] = round(
                float(entry.get("paused_seconds", 0) or 0)
                + _seconds_between(pause_started, now),
                3,
            )

    entry["pause_started"] = None
    entry["stop"] = _iso(now)
    entry["status"] = "completed"
    _refresh_derived(entry, now)
    _save_work_log(log)
    return True


def get_work_log(user_id=None):
    log = _load_work_log()
    if user_id is not None:
        log = [x for x in log if str(x.get("user")) == str(user_id)]
    now = _now()
    for entry in log:
        if entry.get("stop") is None:
            _refresh_derived(entry, now)
    return log


def get_active_work(user_id):
    log = _load_work_log()
    now = _now()
    for entry in reversed(log):
        if (
            str(entry.get("user")) == str(user_id)
            and entry.get("stop") is None
            and entry.get("status", "running") in {"running", "paused"}
        ):
            return _refresh_derived(entry, now)
    return None


def _fmt_seconds(seconds):
    total = max(0, int(seconds or 0))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    return f"{minutes:02d}m {secs:02d}s"


def work_status(user_id):
    entry = get_active_work(user_id)
    if not entry:
        return "⏱️ אין משימת עבודה פעילה."

    _refresh_derived(entry)
    started = entry.get("start", "?")
    try:
        started = _parse(started).strftime("%H:%M:%S")
    except Exception:
        pass

    status = str(entry.get("status", "running")).upper()
    phase = entry.get("phase") or "—"
    return (
        "⏱️ WORK EXECUTION CLOCK\n"
        f"Task: {entry.get('task', '—')}\n"
        f"Started: {started}\n"
        f"Elapsed: {_fmt_seconds(entry.get('wall_seconds'))}\n"
        f"Active: {_fmt_seconds(entry.get('active_seconds'))}\n"
        f"Paused: {_fmt_seconds(entry.get('paused_seconds'))}\n"
        f"Status: {status}\n"
        f"Phase: {phase}"
    )


def work_report(user_id=None):
    entries = get_work_log(user_id)
    completed = [e for e in entries if e.get("stop")]
    active = [e for e in entries if not e.get("stop")]
    active_seconds = sum(float(e.get("active_seconds", 0) or 0) for e in entries)
    wall_seconds = sum(float(e.get("wall_seconds", 0) or 0) for e in entries)
    paused_seconds = sum(float(e.get("paused_seconds", 0) or 0) for e in entries)

    lines = [
        "📊 SLH OS WORK REPORT",
        "",
        f"Sessions: {len(entries)}",
        f"Completed: {len(completed)}",
        f"Running: {len(active)}",
        f"Active work: {_fmt_seconds(active_seconds)}",
        f"Wall time: {_fmt_seconds(wall_seconds)}",
        f"Paused: {_fmt_seconds(paused_seconds)}",
    ]

    if active:
        lines += ["", "⏱️ ACTIVE NOW"]
        for entry in active[-3:]:
            _refresh_derived(entry)
            lines.append(
                f"• {entry.get('task', '—')} — "
                f"{_fmt_seconds(entry.get('active_seconds'))} active / "
                f"{_fmt_seconds(entry.get('wall_seconds'))} elapsed "
                f"[{str(entry.get('status', 'running')).upper()}]"
            )
    return "\n".join(lines)


def progress_report():
    db = _load_db()
    tasks = db.get("tasks", {})
    total = sum(t.get("progress", 0) for t in tasks.values())
    count = len(tasks)
    overall = int(total / count) if count else 0
    lines = [f"📊 SLH PROGRESS — OVERALL {overall}%", ""]
    for task_id, task in tasks.items():
        title = task.get("title", task_id)
        progress = task.get("progress", 0)
        status = task.get("status", "active")
        lines.append(f"{title:25} {status:8} {progress}%")
    lines.append("")
    lines.append(f"🕒 {_now().strftime('%Y-%m-%d %H:%M:%S')}")
    return "\n".join(lines)
