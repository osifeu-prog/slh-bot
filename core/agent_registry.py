from datetime import datetime

import state_manager
from core.audit import log_event
from core.agent_state_store import AgentStateStore
from core.agent_policy import can_create_agent

STORE = AgentStateStore()


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


def create_agent(name, role="agent", owner_id=None, runtime_class="EchoAgent"):
    """
    Create a new agent in the canonical DB with an explicit safe runtime class.

    EchoAgent is the default personal/runtime-safe implementation currently
    registered by core.agent_factory. Callers that need another manifested
    runtime must pass it explicitly.
    """
    name = str(name).strip()
    if not name:
        raise ValueError("Agent name cannot be empty")

    runtime_class = str(runtime_class).strip()
    if not runtime_class:
        raise ValueError("Agent runtime_class cannot be empty")

    agents = STORE.get_all()
    for agent_id, agent in agents.items():
        if str(agent.get("name", "")).lower() == name.lower():
            if owner_id is not None and str(agent.get("owner_id", "")) == str(owner_id):
                if not agent.get("runtime_class"):
                    db = STORE._load_db()
                    existing = db.setdefault("agents", {}).get(str(agent_id))
                    if existing is not None:
                        existing["runtime_class"] = runtime_class
                        STORE._atomic_write(STORE.DB_PATH, db)
                        STORE.rebuild_snapshot(db=db)
                        agent = existing
                        log_event(
                            "agent.runtime_repaired",
                            target=str(agent_id),
                            details={"runtime_class": runtime_class},
                        )
                return str(agent.get("id", agent_id)), agent
            raise ValueError(f"Agent '{name}' already exists")

    if owner_id is not None:
        owned_count = sum(
            1 for agent in agents.values()
            if str(agent.get("owner_id", "")) == str(owner_id)
        )
        if not can_create_agent(owner_id, owned_count):
            raise ValueError("AGENT_LIMIT_REACHED")

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
        "runtime_class": runtime_class,
        "inbox": [],
        "history": [],
        "permissions": [],
        "created": datetime.now().isoformat(),
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


def update_agent(identifier, **changes):
    agent_id, agent = get_agent(identifier)
    if agent is None:
        raise KeyError(f"Agent '{identifier}' not found")
    db = STORE._load_db()
    target = db.setdefault("agents", {}).get(agent_id)
    if target is None:
        raise KeyError(f"Agent '{identifier}' not found")
    target.update(changes)
    STORE._atomic_write(STORE.DB_PATH, db)
    STORE.rebuild_snapshot(db=db)
    log_event("agent.updated", target=agent_id, details={"fields": list(changes.keys())})
    return agent_id, target


def delete_agent(identifier):
    agent_id, agent = get_agent(identifier)
    if agent is None:
        raise KeyError(f"Agent '{identifier}' not found")
    db = STORE._load_db()
    agents = db.setdefault("agents", {})
    if agent_id not in agents:
        raise KeyError(f"Agent '{identifier}' not found")
    del agents[agent_id]
    STORE._atomic_write(STORE.DB_PATH, db)
    STORE.rebuild_snapshot(db=db)
    log_event("agent.deleted", target=agent_id)
    return agent_id


def send_message(identifier, message):
    """Append a string or structured command to an agent inbox atomically."""
    agent_id, agent = get_agent(identifier)
    if agent is None:
        raise KeyError(f"Agent '{identifier}' not found")

    payload = dict(message) if isinstance(message, dict) else str(message)
    request_id = (
        str(payload.get("request_id") or "").strip()
        if isinstance(payload, dict)
        else ""
    )
    queued = {"value": False}

    def mutate(db):
        agents = db.get("agents", {})
        target = agents.get(agent_id) if isinstance(agents, dict) else None
        if not isinstance(target, dict):
            raise KeyError(f"Agent '{identifier}' not found")
        inbox = target.setdefault("inbox", [])
        if not isinstance(inbox, list):
            raise ValueError("AGENT_INBOX_INVALID")

        if request_id:
            processing = target.get("processing", [])
            already_pending = any(
                isinstance(item, dict) and str(item.get("request_id") or "") == request_id
                for item in inbox
            )
            already_processing = any(
                isinstance(item, dict)
                and isinstance(item.get("message"), dict)
                and str(item["message"].get("request_id") or "") == request_id
                for item in (processing if isinstance(processing, list) else [])
            )
            if already_pending or already_processing:
                return False

        inbox.append(payload)
        queued["value"] = True
        return True

    state_manager.atomic_update(mutate)
    if queued["value"]:
        STORE.rebuild_snapshot()
        log_event(
            "agent.message_sent",
            target=agent_id,
            details={
                "message_length": len(str(payload)),
                "structured": isinstance(payload, dict),
            },
        )
    return agent_id


def get_inbox(identifier):
    agent_id, agent = get_agent(identifier)
    if agent is None:
        raise KeyError(f"Agent '{identifier}' not found")
    return agent_id, list(agent.get("inbox", []))


def get_outbox(identifier, limit=5):
    """Return the newest bounded agent results for an authorized caller."""
    agent_id, agent = get_agent(identifier)
    if agent is None:
        raise KeyError(f"Agent '{identifier}' not found")
    try:
        count = max(1, min(int(limit), 20))
    except (TypeError, ValueError, OverflowError):
        count = 5
    outbox = agent.get("outbox", [])
    if not isinstance(outbox, list):
        return agent_id, []
    return agent_id, list(outbox[-count:])
