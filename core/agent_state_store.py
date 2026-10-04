#!/usr/bin/env python3

import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

import state_manager


class AgentStateStore:
    ROOT = Path(__file__).resolve().parent.parent
    DB_PATH = ROOT / "state" / "db.json"
    SNAPSHOT_PATH = ROOT / "state" / "agents.json"

    _lock = threading.RLock()

    VALID_STATES = {"idle", "active", "error"}

    def __init__(self):
        self.DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    def _now(self):
        return datetime.now(timezone.utc).isoformat()

    def _load_db(self):
        # Compatibility helper; canonical locking/error semantics live in state_manager.
        return state_manager.load_db()

    def _atomic_write(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=str(path.parent),
        )
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, path)
        finally:
            temp_path.unlink(missing_ok=True)

    def _normalize_agent(self, agent_id, agent):
        result = dict(agent)
        result["id"] = str(result.get("id", agent_id))
        result.setdefault("name", f"Agent-{agent_id}")
        result.setdefault("role", "agent")
        result.setdefault("state", "idle")
        return result

    def get_all(self):
        with self._lock:
            db = state_manager.load_db()
            return {
                str(agent_id): self._normalize_agent(agent_id, agent)
                for agent_id, agent in db.get("agents", {}).items()
                if isinstance(agent, dict)
            }

    def get(self, identifier):
        identifier = str(identifier)
        agents = self.get_all()
        if identifier in agents:
            return agents[identifier]
        for agent_id, agent in agents.items():
            if str(agent.get("name", "")).lower() == identifier.lower():
                return agent
        return None

    def update_state(self, identifier, state):
        state = str(state).lower()
        if state not in self.VALID_STATES:
            raise ValueError(f"Invalid agent state: {state}")

        result = {}
        with self._lock:
            def mutate(db):
                agents = db.setdefault("agents", {})
                identifier_text = str(identifier)
                target_id = None

                if identifier_text in agents:
                    target_id = identifier_text
                else:
                    for agent_id, agent in agents.items():
                        if (
                            isinstance(agent, dict)
                            and str(agent.get("name", "")).lower()
                            == identifier_text.lower()
                        ):
                            target_id = str(agent_id)
                            break

                if target_id is None:
                    raise KeyError(f"Agent not found: {identifier}")

                old_state = agents[target_id].get("state")
                agents[target_id]["state"] = state
                agents[target_id]["state_updated_at"] = self._now()
                result.update({
                    "agent_id": target_id,
                    "old_state": old_state,
                    "new_state": state,
                    "changed": old_state != state,
                    "updated_at": self._now(),
                    "agents": {
                        str(agent_id): self._normalize_agent(agent_id, agent)
                        for agent_id, agent in agents.items()
                        if isinstance(agent, dict)
                    },
                })

            state_manager.atomic_update(mutate)
            snapshot_data = result.pop("agents", {})
            self.rebuild_snapshot(snapshot_data)
            return result

    def rebuild_snapshot(self, db=None):
        with self._lock:
            if db is None:
                db = state_manager.load_db()

            agents = db.get("agents", {}) if isinstance(db, dict) else {}
            snapshot = {
                str(agent_id): self._normalize_agent(agent_id, agent)
                for agent_id, agent in agents.items()
                if isinstance(agent, dict)
            }
            self._atomic_write(self.SNAPSHOT_PATH, snapshot)
            return snapshot

    def audit(self):
        with self._lock:
            db_agents = self.get_all()
            snapshot = {}

            if self.SNAPSHOT_PATH.exists():
                with self.SNAPSHOT_PATH.open("r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    snapshot = loaded

            db_ids = set(db_agents)
            snapshot_ids = set(map(str, snapshot))
            issues = []

            for agent_id in db_ids | snapshot_ids:
                db_agent = db_agents.get(agent_id, {})
                snapshot_agent = snapshot.get(agent_id, {})
                if db_agent.get("state") != snapshot_agent.get("state"):
                    issues.append({
                        "agent_id": agent_id,
                        "type": "state_drift",
                        "db_state": db_agent.get("state"),
                        "snapshot_state": snapshot_agent.get("state"),
                    })

            return {
                "ok": len(issues) == 0,
                "db_count": len(db_ids),
                "snapshot_count": len(snapshot_ids),
                "issues": issues,
                "checked_at": self._now(),
            }


if __name__ == "__main__":
    store = AgentStateStore()
    print("=" * 80)
    print("AGENT STATE STORE SELF-TEST")
    print("=" * 80)
    print()
    print("DB:", store.DB_PATH)
    print("SNAPSHOT:", store.SNAPSHOT_PATH)
    print()
    print("AGENTS:")
    for agent_id, agent in store.get_all().items():
        print(agent_id, "|", agent.get("name"), "|", agent.get("state"))
    print()
    print("AUDIT:")
    print(json.dumps(store.audit(), indent=2, ensure_ascii=False))
    print()
    print("=" * 80)
    print("SELF-TEST COMPLETE")
    print("READ/WRITE API READY")
    print("=" * 80)
