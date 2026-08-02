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
    with open(DB_FILE) as f:
        return json.load(f)

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

AGENTS_FILE = "state/db.json"


def get_agents():
    try:
        db = load_db()
        return db.get("agents", {})
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
