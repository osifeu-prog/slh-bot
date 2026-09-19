import json
import os
import fcntl

try:
    with open("config.json") as f:
        cfg = json.load(f)
except:
    cfg = {}
DB_FILE = cfg.get("DB_FILE", "state/db.json")

def load_db():
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


def save_db(db):
    if not isinstance(db, dict) or "users" not in db:
        raise ValueError("save_db refused: malformed db")
    if not db["users"]:
        raise ValueError("save_db refused: empty users - possible wipe")
    os.makedirs(os.path.dirname(DB_FILE) or ".", exist_ok=True)
    tmp = DB_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, DB_FILE)


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

try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False

_LOCK_PATH = DB_FILE + ".lock"

def atomic_update(mutate_fn):
    """
    Safely load, mutate, and save the DB as one atomic operation.
    mutate_fn receives the db dict, modifies it in place, and returns a result.
    """
    os.makedirs("state", exist_ok=True)
    with open(_LOCK_PATH, "w") as lockfile:
        if HAS_FCNTL:
            fcntl.flock(lockfile, fcntl.LOCK_EX)
        try:
            db = load_db()
            result = mutate_fn(db)
            save_db(db)
            return result
        finally:
            if HAS_FCNTL:
                fcntl.flock(lockfile, fcntl.LOCK_UN)



def load_json(filename, default=None):
    """Read a JSON state file without mutating it."""
    path = filename if os.path.isabs(filename) else os.path.join("state", filename)
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def atomic_json_update(filename, mutate_fn, default=None):
    """Atomically update a JSON file under state/ with its own lock."""
    path = filename if os.path.isabs(filename) else os.path.join("state", filename)
    lock_path = path + ".lock"
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(lock_path, "a+", encoding="utf-8") as lockfile:
        if HAS_FCNTL:
            fcntl.flock(lockfile, fcntl.LOCK_EX)
        try:
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = default if default is not None else {}
            result = mutate_fn(data)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
            return result
        finally:
            if HAS_FCNTL:
                fcntl.flock(lockfile, fcntl.LOCK_UN)

