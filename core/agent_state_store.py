#!/usr/bin/env python3

import json
import os
import tempfile
import threading
from pathlib import Path
from datetime import datetime, timezone


class AgentStateStore:

    ROOT = Path(__file__).resolve().parent.parent

    DB_PATH = ROOT / "state" / "db.json"
    SNAPSHOT_PATH = ROOT / "state" / "agents.json"

    _lock = threading.RLock()

    VALID_STATES = {
        "idle",
        "active",
        "error",
    }

    def __init__(self):
        self.DB_PATH.parent.mkdir(
            parents=True,
            exist_ok=True
        )

    # -------------------------------------------------
    # INTERNAL
    # -------------------------------------------------

    def _now(self):
        return datetime.now(
            timezone.utc
        ).isoformat()

    def _load_db(self):

        if not self.DB_PATH.exists():
            raise FileNotFoundError(
                f"DB not found: {self.DB_PATH}"
            )

        with self.DB_PATH.open(
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError(
                "DB root must be a JSON object"
            )

        if not isinstance(
            data.get("agents"),
            dict
        ):
            data["agents"] = {}

        return data

    def _atomic_write(self, path, data):

        path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        fd, temp_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=str(path.parent)
        )

        try:

            with os.fdopen(
                fd,
                "w",
                encoding="utf-8"
            ) as f:

                json.dump(
                    data,
                    f,
                    indent=2,
                    ensure_ascii=False
                )

                f.write("\n")
                f.flush()
                os.fsync(f.fileno())

            os.replace(
                temp_name,
                path
            )

        except Exception:

            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass

            raise

    def _normalize_agent(
        self,
        agent_id,
        agent
    ):

        result = dict(agent)

        result["id"] = str(
            result.get(
                "id",
                agent_id
            )
        )

        result.setdefault(
            "name",
            f"Agent-{agent_id}"
        )

        result.setdefault(
            "role",
            "agent"
        )

        result.setdefault(
            "state",
            "idle"
        )

        return result

    # -------------------------------------------------
    # READ
    # -------------------------------------------------

    def get_all(self):

        with self._lock:

            db = self._load_db()

            return {
                str(agent_id):
                self._normalize_agent(
                    agent_id,
                    agent
                )

                for agent_id, agent
                in db["agents"].items()

                if isinstance(agent, dict)
            }

    def get(self, identifier):

        identifier = str(identifier)

        agents = self.get_all()

        if identifier in agents:
            return agents[identifier]

        for agent_id, agent in agents.items():

            if str(
                agent.get("name", "")
            ).lower() == identifier.lower():

                return agent

        return None

    # -------------------------------------------------
    # WRITE
    # -------------------------------------------------

    def update_state(
        self,
        identifier,
        state
    ):

        state = str(state).lower()

        if state not in self.VALID_STATES:

            raise ValueError(
                f"Invalid agent state: {state}"
            )

        with self._lock:

            db = self._load_db()

            agents = db["agents"]

            target_id = None

            identifier = str(identifier)

            if identifier in agents:
                target_id = identifier

            else:

                for agent_id, agent in agents.items():

                    if (
                        isinstance(agent, dict)
                        and str(
                            agent.get(
                                "name",
                                ""
                            )
                        ).lower()
                        == identifier.lower()
                    ):

                        target_id = str(
                            agent_id
                        )

                        break

            if target_id is None:

                raise KeyError(
                    f"Agent not found: {identifier}"
                )

            old_state = agents[
                target_id
            ].get(
                "state"
            )

            agents[
                target_id
            ]["state"] = state

            agents[
                target_id
            ]["state_updated_at"] = self._now()

            self._atomic_write(
                self.DB_PATH,
                db
            )

            self.rebuild_snapshot(
                db=db
            )

            return {
                "agent_id": target_id,
                "old_state": old_state,
                "new_state": state,
                "changed": old_state != state,
                "updated_at": self._now()
            }

    # -------------------------------------------------
    # SNAPSHOT
    # -------------------------------------------------

    def rebuild_snapshot(
        self,
        db=None
    ):

        with self._lock:

            if db is None:
                db = self._load_db()

            snapshot = {}

            for agent_id, agent in db.get(
                "agents",
                {}
            ).items():

                if not isinstance(
                    agent,
                    dict
                ):
                    continue

                snapshot[
                    str(agent_id)
                ] = self._normalize_agent(
                    agent_id,
                    agent
                )

            self._atomic_write(
                self.SNAPSHOT_PATH,
                snapshot
            )

            return snapshot

    # -------------------------------------------------
    # AUDIT
    # -------------------------------------------------

    def audit(self):

        with self._lock:

            db_agents = self.get_all()

            snapshot = {}

            if self.SNAPSHOT_PATH.exists():

                with self.SNAPSHOT_PATH.open(
                    "r",
                    encoding="utf-8"
                ) as f:

                    loaded = json.load(f)

                if isinstance(
                    loaded,
                    dict
                ):

                    snapshot = loaded

            db_ids = set(
                db_agents
            )

            snapshot_ids = set(
                map(
                    str,
                    snapshot
                )
            )

            issues = []

            for agent_id in (
                db_ids
                | snapshot_ids
            ):

                db_agent = db_agents.get(
                    agent_id,
                    {}
                )

                snapshot_agent = snapshot.get(
                    agent_id,
                    {}
                )

                db_state = db_agent.get(
                    "state"
                )

                snapshot_state = snapshot_agent.get(
                    "state"
                )

                if db_state != snapshot_state:

                    issues.append(
                        {
                            "agent_id": agent_id,
                            "type": "state_drift",
                            "db_state": db_state,
                            "snapshot_state": snapshot_state
                        }
                    )

            return {
                "ok": len(issues) == 0,
                "db_count": len(db_ids),
                "snapshot_count": len(snapshot_ids),
                "issues": issues,
                "checked_at": self._now()
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

        print(
            agent_id,
            "|",
            agent.get("name"),
            "|",
            agent.get("state")
        )

    print()
    print("AUDIT:")

    print(
        json.dumps(
            store.audit(),
            indent=2,
            ensure_ascii=False
        )
    )

    print()
    print("=" * 80)
    print("SELF-TEST COMPLETE")
    print("READ/WRITE API READY")
    print("NO RUNTIME INTEGRATION YET")
    print("=" * 80)
