import json
import os
import tempfile
import threading
from contextlib import contextmanager

try:
    with open("config.json") as f:
        cfg = json.load(f)
except Exception:
    cfg = {}

DB_FILE = cfg.get("DB_FILE", "state/db.json")

# Thread-local serialization inside one process. File locks below add
# cross-process serialization on POSIX systems.
_THREAD_LOCK = threading.RLock()

try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    fcntl = None
    HAS_FCNTL = False

_LOCK_PATH = DB_FILE + ".lock"


@contextmanager
def _file_lock(lock_path):
    os.makedirs(os.path.dirname(lock_path) or ".", exist_ok=True)
    with open(lock_path, "a+", encoding="utf-8") as lockfile:
        if HAS_FCNTL:
            fcntl.flock(lockfile, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if HAS_FCNTL:
                fcntl.flock(lockfile, fcntl.LOCK_UN)


def _load_db_unlocked():
    if not os.path.exists(DB_FILE):
        return {
            "users": {}, "students": {}, "courses": {}, "admins": [],
            "agents": {}, "tasks": {}, "memory": {}, "votes": {}
        }
    with open(DB_FILE, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or "users" not in data:
        raise RuntimeError("load_db: db.json corrupt - refusing to continue")
    return data


def _write_json_atomic(path, data):
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=os.path.basename(path) + ".tmp-",
        dir=directory,
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
        # Best-effort directory fsync so the rename is durable on filesystems
        # that support it. Ignore platforms/filesystems where this is not valid.
        try:
            dir_fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except (OSError, ValueError):
            pass
    except Exception:
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        raise


def load_db():
    with _THREAD_LOCK:
        with _file_lock(_LOCK_PATH):
            return _load_db_unlocked()


def save_db(db):
    if not isinstance(db, dict) or "users" not in db:
        raise ValueError("save_db refused: malformed db")
    if not db["users"]:
        raise ValueError("save_db refused: empty users - possible wipe")
    with _THREAD_LOCK:
        with _file_lock(_LOCK_PATH):
            _write_json_atomic(DB_FILE, db)


def get_agents():
    from core.agent_state_store import AgentStateStore
    store = AgentStateStore()
    return store.get_all()


def set_agents(agents):
    db = load_db()
    db["agents"] = agents
    save_db(db)


def update_agent(prefix, data):
    agents = get_agents()
    agents[prefix] = data
    set_agents(agents)


def delete_agent(prefix):
    agents = get_agents()
    if prefix in agents:
        del agents[prefix]
        set_agents(agents)


def clear_agents():
    set_agents({})


def atomic_update(mutate_fn):
    """
    Safely load, mutate, and save the DB as one atomic operation.

    The callback executes while the DB file lock is held, preventing another
    process from loading a stale snapshot and overwriting this transaction.
    """
    if not callable(mutate_fn):
        raise TypeError("atomic_update requires a callable")
    with _THREAD_LOCK:
        with _file_lock(_LOCK_PATH):
            db = _load_db_unlocked()
            result = mutate_fn(db)
            if not isinstance(db, dict) or "users" not in db:
                raise ValueError("atomic_update refused: malformed db")
            if not db["users"]:
                raise ValueError("atomic_update refused: empty users - possible wipe")
            _write_json_atomic(DB_FILE, db)
            return result


def load_json(filename, default=None):
    """Read a JSON state file without mutating it."""
    path = filename if os.path.isabs(filename) else os.path.join("state", filename)
    if not os.path.exists(path):
        return default
    with _THREAD_LOCK:
        with _file_lock(path + ".lock"):
            if not os.path.exists(path):
                return default
            with open(path, encoding="utf-8") as f:
                return json.load(f)


def atomic_json_update(filename, mutate_fn, default=None):
    """Atomically update a JSON file under state/ with its own lock."""
    if not callable(mutate_fn):
        raise TypeError("atomic_json_update requires a callable")
    path = filename if os.path.isabs(filename) else os.path.join("state", filename)
    lock_path = path + ".lock"
    with _THREAD_LOCK:
        with _file_lock(lock_path):
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = default if default is not None else {}
            result = mutate_fn(data)
            _write_json_atomic(path, data)
            return result
