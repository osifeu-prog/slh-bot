"""Explicit allow-list for bounded mission side effects."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Optional


@dataclass(frozen=True)
class ExecutionResult:
    mission_id: str
    action_type: str
    status: str
    started_at: str
    completed_at: str
    idempotency_key: str
    evidence: Mapping[str, Any] = field(default_factory=dict)
    verified: bool = False
    error: Optional[str] = None

    def as_dict(self):
        return {
            "mission_id": self.mission_id,
            "action_type": self.action_type,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "idempotency_key": self.idempotency_key,
            "evidence": dict(self.evidence),
            "verified": self.verified,
            "error": self.error,
        }


class MissionActionRegistry:
    def __init__(self):
        self._actions = {}

    def register(self, action_type: str, handler: Callable[..., Mapping[str, Any]]):
        action_type = str(action_type).strip()
        if not action_type or not callable(handler):
            raise ValueError("INVALID_MISSION_ACTION")
        if action_type in self._actions:
            raise ValueError("MISSION_ACTION_ALREADY_REGISTERED")
        self._actions[action_type] = handler

    def supports(self, action_type: str) -> bool:
        return str(action_type).strip() in self._actions

    def execute(self, action_type, *, mission_id, payload, context, idempotency_key):
        action_type = str(action_type).strip()
        now = datetime.now(timezone.utc).isoformat()
        if not self.supports(action_type):
            return ExecutionResult(
                str(mission_id), action_type, "blocked", now, now,
                str(idempotency_key), verified=False, error="unsupported_action"
            )

        started = now
        try:
            raw = self._actions[action_type](
                payload=dict(payload or {}),
                context=dict(context or {}),
                mission_id=str(mission_id),
                idempotency_key=str(idempotency_key),
            )
            result = dict(raw or {})
            completed = datetime.now(timezone.utc).isoformat()
            verified = result.get("verified") is True and bool(result.get("evidence"))
            return ExecutionResult(
                str(mission_id), action_type,
                "success" if verified else "blocked",
                started, completed, str(idempotency_key),
                evidence=result.get("evidence", {}),
                verified=verified,
                error=result.get("error"),
            )
        except Exception as exc:
            completed = datetime.now(timezone.utc).isoformat()
            return ExecutionResult(
                str(mission_id), action_type, "blocked", started, completed,
                str(idempotency_key), verified=False, error=type(exc).__name__
            )


def build_default_registry():
    return MissionActionRegistry()
