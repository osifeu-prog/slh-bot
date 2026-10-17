from datetime import datetime
from typing import Any

import state_manager
from core.audit import log_event
from core.agent_state_store import AgentStateStore
from core.agent_policy import can_create_agent

STORE = AgentStateStore()


def load_agents():
    return STORE.get_all()


def list_agents():
    return STORE.get_all()


def _resolve_agent_id(agents: dict, identifier: Any) -> str | None:
    """Resolve an agent by canonical ID or display name inside the locked DB view."""
    value = str(identifier)
    if value in agents and isinstance(agents.get(value), dict):
        return value
    for agent_id, record in agents.items():
        if (
            isinstance(record, dict)
            and str(record.get("name", "")).casefold() == value.casefold()
        ):
            return str(agent_id)
    return None


def get_agent(identifier):
    identifier = str(identifier)
    agent = STORE.get(identifier)
    if agent is None:
        return None, None
    return str(agent.get("id", identifier)), agent


def create_agent(name, role="agent", owner_id=None, runtime_class="EchoAgent"):
    """Create or repair an agent through the canonical shared-lock state API."""
    name = str(name).strip()
    if not name:
        raise ValueError("Agent name cannot be empty")

    runtime_class = str(runtime_class).strip()
    if not runtime_class:
        raise ValueError("Agent runtime_class cannot be empty")

    normalized_owner = str(owner_id) if owner_id is not None else None

    def mutate(db):
        agents = db.setdefault("agents", {})
        if not isinstance(agents, dict):
            raise ValueError("agents must be an object")

        for agent_id, existing in agents.items():
            if not isinstance(existing, dict):
                continue
            if str(existing.get("name", "")).casefold() != name.casefold():
                continue

            if normalized_owner is not None and str(
                existing.get("owner_id", "")
            ) == normalized_owner:
                repaired = not str(existing.get("runtime_class") or "").strip()
                if repaired:
                    existing["runtime_class"] = runtime_class
                return {
                    "agent_id": str(existing.get("id", agent_id)),
                    "agent": dict(existing),
                    "action": "repaired" if repaired else "existing",
                    "runtime_class": runtime_class,
                }

            raise ValueError(f"Agent '{name}' already exists")

        if normalized_owner is not None:
            owned_count = sum(
                1 for record in agents.values()
                if isinstance(record, dict)
                and str(record.get("owner_id", "")) == normalized_owner
            )
            if not can_create_agent(normalized_owner, owned_count):
                raise ValueError("AGENT_LIMIT_REACHED")

        numeric_ids = []
        for key in agents:
            try:
                numeric_ids.append(int(key))
            except (TypeError, ValueError):
                continue
        next_id = str(max(numeric_ids, default=0) + 1)

        agent = {
            "id": next_id,
            "name": name,
            "state": "idle",
            "role": role,
            "owner_id": normalized_owner,
            "runtime_class": runtime_class,
            "inbox": [],
            "history": [],
            "permissions": [],
            "created": datetime.now().isoformat(),
        }
        agents[next_id] = agent
        return {
            "agent_id": next_id,
            "agent": dict(agent),
            "action": "created",
            "runtime_class": runtime_class,
        }

    result = state_manager.atomic_update(mutate)
    if result["action"] in {"created", "repaired"}:
        STORE.rebuild_snapshot()
    if result["action"] == "created":
        log_event(
            "agent.created",
            target=result["agent_id"],
            details={
                "name": name,
                "role": role,
                "runtime_class": runtime_class,
            },
        )
    elif result["action"] == "repaired":
        log_event(
            "agent.runtime_repaired",
            target=result["agent_id"],
            details={"runtime_class": runtime_class},
        )
    return result["agent_id"], result["agent"]


def update_agent(identifier, **changes):
    def mutate(db):
        agents = db.setdefault("agents", {})
        if not isinstance(agents, dict):
            raise ValueError("agents must be an object")
        agent_id = _resolve_agent_id(agents, identifier)
        if agent_id is None:
            raise KeyError(f"Agent '{identifier}' not found")
        target = agents[agent_id]
        target.update(changes)
        return str(target.get("id", agent_id)), dict(target)

    agent_id, target = state_manager.atomic_update(mutate)
    STORE.rebuild_snapshot()
    log_event(
        "agent.updated",
        target=agent_id,
        details={"fields": list(changes.keys())},
    )
    return agent_id, target


def delete_agent(identifier):
    def mutate(db):
        agents = db.setdefault("agents", {})
        if not isinstance(agents, dict):
            raise ValueError("agents must be an object")
        agent_id = _resolve_agent_id(agents, identifier)
        if agent_id is None:
            raise KeyError(f"Agent '{identifier}' not found")
        deleted = agents.pop(agent_id)
        return str(deleted.get("id", agent_id)), dict(deleted)

    agent_id, deleted = state_manager.atomic_update(mutate)
    STORE.rebuild_snapshot()
    log_event("agent.deleted", target=agent_id)
    # The Telegram handler unpacks (agent_id, deleted_agent); keep that contract.
    return agent_id, deleted


def send_message(identifier, message):
    """Append a legacy text message or structured worker task atomically.

    Structured task request IDs are idempotency keys while that request is
    still queued or leased for processing. This prevents Telegram retries from
    enqueueing the same task twice without suppressing a later intentional ask.
    """
    if isinstance(message, dict):
        payload = dict(message)
        if not isinstance(payload.get("command"), str) or not payload["command"].strip():
            raise ValueError("INVALID_AGENT_MESSAGE")
        payload["command"] = payload["command"].strip()
    else:
        payload = str(message)

    request_id = (
        str(payload.get("request_id") or "").strip()
        if isinstance(payload, dict)
        else ""
    )
    queued = {"value": False}

    def mutate(db):
        agents = db.setdefault("agents", {})
        if not isinstance(agents, dict):
            raise ValueError("agents must be an object")
        agent_id = _resolve_agent_id(agents, identifier)
        if agent_id is None:
            raise KeyError(f"Agent '{identifier}' not found")
        agent = agents[agent_id]
        inbox = agent.setdefault("inbox", [])
        processing = agent.setdefault("processing", [])
        if not isinstance(inbox, list):
            raise ValueError(f"invalid inbox for agent {agent_id}")
        if not isinstance(processing, list):
            raise ValueError(f"invalid processing queue for agent {agent_id}")

        if request_id:
            already_pending = any(
                isinstance(item, dict)
                and str(item.get("request_id") or "").strip() == request_id
                for item in inbox
            )
            already_processing = any(
                isinstance(item, dict)
                and isinstance(item.get("message"), dict)
                and str(item["message"].get("request_id") or "").strip() == request_id
                for item in processing
            )
            if already_pending or already_processing:
                return str(agent.get("id", agent_id))

        inbox.append(payload)
        queued["value"] = True
        return str(agent.get("id", agent_id))

    agent_id = state_manager.atomic_update(mutate)
    if queued["value"]:
        STORE.rebuild_snapshot()
        log_event(
            "agent.message_sent",
            target=agent_id,
            details={
                "message_length": len(str(message)),
                "message_type": "structured" if isinstance(message, dict) else "text",
                "request_id_deduplicated": bool(request_id),
            },
        )
    return agent_id


def get_inbox(identifier):
    agent_id, agent = get_agent(identifier)
    if agent is None:
        raise KeyError(f"Agent '{identifier}' not found")
    return agent_id, list(agent.get("inbox", []))
