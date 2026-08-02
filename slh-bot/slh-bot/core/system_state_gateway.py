#!/usr/bin/env python3

"""
SLH System State Gateway

Single read boundary for system state.

Phase 1:
- Read-only
- No migration
- No restart
- No destructive operations

The Gateway aggregates existing state sources without changing them.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.agent_state_store import AgentStateStore


ROOT = Path(__file__).resolve().parent.parent

DB_PATH = ROOT / "state" / "db.json"
AGENTS_PATH = ROOT / "state" / "agents.json"


def now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


class SystemStateGateway:

    def __init__(self):

        self.agent_store = AgentStateStore()

    # -------------------------------------------------
    # SAFE JSON READ
    # -------------------------------------------------

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:

        if not path.exists():

            return {
                "_error": "FILE_NOT_FOUND",
                "_path": str(path),
            }

        try:

            with path.open(
                "r",
                encoding="utf-8"
            ) as f:

                data = json.load(f)

            if isinstance(data, dict):

                return data

            return {
                "_error": "INVALID_ROOT_TYPE",
                "_path": str(path),
            }

        except Exception as exc:

            return {
                "_error": "READ_FAILED",
                "_path": str(path),
                "_exception": repr(exc),
            }

    # -------------------------------------------------
    # AGENTS
    # -------------------------------------------------

    def agents(self) -> dict[str, Any]:

        try:

            agents = self.agent_store.get_all()

            states = {}

            for agent in agents.values():

                state = agent.get(
                    "state",
                    "unknown"
                )

                states[state] = (
                    states.get(state, 0) + 1
                )

            return {
                "total": len(agents),
                "states": states,
                "items": agents,
                "source": (
                    "AgentStateStore"
                ),
            }

        except Exception as exc:

            return {
                "total": 0,
                "states": {},
                "items": {},
                "error": repr(exc),
            }

    # -------------------------------------------------
    # DATABASE SUMMARY
    # -------------------------------------------------

    def database(self) -> dict[str, Any]:

        db = self._read_json(
            DB_PATH
        )

        if "_error" in db:

            return db

        summary = {}

        for key, value in db.items():

            if isinstance(value, dict):

                summary[key] = {
                    "type": "dict",
                    "count": len(value),
                }

            elif isinstance(value, list):

                summary[key] = {
                    "type": "list",
                    "count": len(value),
                }

            else:

                summary[key] = {
                    "type": type(value).__name__,
                }

        return {
            "sections": summary,
            "source": "state/db.json",
        }

    # -------------------------------------------------
    # USERS
    # -------------------------------------------------

    def users(self) -> dict[str, Any]:

        db = self._read_json(
            DB_PATH
        )

        users = db.get(
            "users",
            {}
        )

        if isinstance(users, dict):

            return {
                "total": len(users),
                "source": "state/db.json",
            }

        if isinstance(users, list):

            return {
                "total": len(users),
                "source": "state/db.json",
            }

        return {
            "total": 0,
            "source": "state/db.json",
        }

    # -------------------------------------------------
    # TASKS
    # -------------------------------------------------

    def tasks(self) -> dict[str, Any]:

        db = self._read_json(
            DB_PATH
        )

        tasks = db.get(
            "tasks",
            {}
        )

        if isinstance(tasks, dict):

            return {
                "total": len(tasks),
                "source": "state/db.json",
            }

        if isinstance(tasks, list):

            return {
                "total": len(tasks),
                "source": "state/db.json",
            }

        return {
            "total": 0,
            "source": "state/db.json",
        }

    # -------------------------------------------------
    # SYSTEM SUMMARY
    # -------------------------------------------------

    def collect(self) -> dict[str, Any]:

        agents = self.agents()

        return {
            "collected_at": now(),

            "system": {
                "status": "operational",
                "gateway": "active",
                "mode": "read_only",
            },

            "agents": {
                "total": agents.get(
                    "total",
                    0
                ),
                "states": agents.get(
                    "states",
                    {}
                ),
            },

            "users": self.users(),

            "tasks": self.tasks(),

            "database": self.database(),

            "sources": {
                "agent_state": (
                    "core.agent_state_store"
                ),
                "database": (
                    "state/db.json"
                ),
            },
        }


def get_system_state() -> dict[str, Any]:

    return SystemStateGateway().collect()


if __name__ == "__main__":

    print(
        json.dumps(
            get_system_state(),
            indent=2,
            ensure_ascii=False
        )
    )
