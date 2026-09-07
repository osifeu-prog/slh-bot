import json
from datetime import datetime
from core.audit import log_event
from core.agent_state_store import AgentStateStore


STORE = AgentStateStore()
DEFAULT_RUNTIME_CLASS = "EchoAgent"


def load_agents():
    return STORE.get_all()


def list_agents():
    return STORE.get_all()


def get_agent(identifier):
    identifier = str(identifier)
    agent = STORE.get(identifier)
    if agent is None:
        return None, None
    return str(agent.get("id", identifier)), agent


def create_agent(name, role="agent", owner_id=None, runtime_class=DEFAULT_RUNTIME_CLASS):
    """Create an agent with an explicitly controlled runtime class."""
    name = str(name).strip()
    if not name:
        raise ValueError("Agent name cannot be empty")

    runtime_class = str(runtime_class or DEFAULT_RUNTIME_CLASS).strip()
    if not runtime_class:
        raise ValueError("Agent runtime_class cannot be empty")

    agents = STORE.get_all()
    for agent_id, agent in agents.items():
        if str(agent.get("name", "")).lower() == name.lower():
            if owner_id is not None and str(agent.get("owner_id", "")) == str(owner_id):
                return str(agent.get("id", agent_id)), agent
            raise ValueError(f"Agent '{name}' already exists")

    numeric_ids = []
    for key in agents:
        try:
            numeric_ids.append(int(key))
        except (TypeError, ValueError):
            pass
    next_id = str(max(numeric_ids, default=0) + 1)

    db = STORE._load_db()
    agent = {
        "id": next_id,
        "name": name,
        "state": "idle",
        "role": role,
        "owner_id": str(owner_id) if owner_id is not None else None,
        "inbox": [],
        "history": [],
        "permissions": [],
        "created": datetime.now().isoformat(),
        "runtime_class": runtime_class,
    }
    db.setdefault("agents", {})[next_id] = agent
    STORE._atomic_write(STORE.DB_PATH, db)
    STORE.rebuild_snapshot(db=db)
    log_event(
        "agent.created",
        target=next_id,
        details={"name": name, "role": role, "runtime_class": runtime_class},
    )
    return next_id, agent


def ensure_runtime_class_defaults():
    """Repair legacy owner-bound agents missing runtime_class."""
    db = STORE._load_db()
    agents = db.setdefault("agents", {})
    repaired = []
    for agent_id, agent in agents.items():
        if not isinstance(agent, dict):
            continue
        if agent.get("runtime_class"):
            continue
        if agent.get("role", "agent") != "agent":
            continue
        if agent.get("owner_id") is None:
            continue
        agent["runtime_class"] = DEFAULT_RUNTIME_CLASS
        repaired.append(str(agent_id))
    if repaired:
        STORE._atomic_write(STORE.DB_PATH, db)
        STORE.rebuild_snapshot(db=db)
    return repaired


def update_agent(identifier, **updates):
    agent_id, agent = get_agent(identifier)
    if agent is None:
        raise KeyError(f"Agent '{identifier}' not found")
    db = STORE._load_db()
    agents = db.setdefault("agents", {})
    if agent_id not in agents:
        raise KeyError(f"Agent '{identifier}' not found")
    agents[agent_id].update(updates)
    STORE._atomic_write(STORE.DB_PATH, db)
    STORE.rebuild_snapshot(db=db)
    log_event("agent.updated", target=agent_id, details={"updates": updates})
    return agent_id, agents[agent_id]


def delete_agent(identifier):
    agent_id, agent = get_agent(identifier)
    if agent is None:
        raise KeyError(f"Agent '{identifier}' not found")
    db = STORE._load_db()
    agents = db.setdefault("agents", {})
    deleted = agents.pop(agent_id)
    STORE._atomic_write(STORE.DB_PATH, db)
    STORE.rebuild_snapshot(db=db)
    log_event("agent.deleted", target=agent_id, details={"name": deleted.get("name")})
    return agent_id, deleted


def send_message(identifier, message):
    agent_id, agent = get_agent(identifier)
    if agent is None:
        raise KeyError(f"Agent '{identifier}' not found")
    db = STORE._load_db()
    agents = db.setdefault("agents", {})
    agents[agent_id].setdefault("inbox", []).append(str(message))
    STORE._atomic_write(STORE.DB_PATH, db)
    STORE.rebuild_snapshot(db=db)
    log_event("agent.message_sent", target=agent_id, details={"message_length": len(str(message))})
    return agent_id


def get_inbox(identifier):
    agent_id, agent = get_agent(identifier)
    if agent is None:
        raise KeyError(f"Agent '{identifier}' not found")
    return list(agent.get("inbox", []))


def sync_snapshot():
    return len(STORE.rebuild_snapshot())


def audit():
    return STORE.audit()
