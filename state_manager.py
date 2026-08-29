import state_manager
import json, os

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
        return json.load(f)

def save_db(db):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

AGENTS_FILE = "state/db.json"


def get_agents():
    try:
        db = load_db()
        return state_manager.get_agents()
    except Exception as e:
        print("Could not load agents:", e)
        return {}


def set_agents(agents):
    try:
        db = load_db()
        db["agents"] = agents
        save_db(db)
    except Exception as e:
        print("Could not save agents:", e)


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


def get_agents():
    from core.agent_state_store import AgentStateStore
    store = AgentStateStore()
    return store.get_all()
