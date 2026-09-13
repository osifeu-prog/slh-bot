"""Allowlisted mission actions and execution evidence.

This module intentionally contains no generic shell or arbitrary callable
execution. Mission actions must be explicitly registered here and return
structured, evidence-bearing results.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Mapping, Optional


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

    def as_dict(self) -> Dict[str, Any]:
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
    """Small explicit allowlist for mission side effects."""

    def __init__(self):
        self._actions: Dict[str, Callable[..., Mapping[str, Any]]] = {}

    def register(self, action_type: str, handler: Callable[..., Mapping[str, Any]]):
        action_type = str(action_type).strip()
        if not action_type or not callable(handler):
            raise ValueError("INVALID_MISSION_ACTION")
        if action_type in self._actions:
            raise ValueError("MISSION_ACTION_ALREADY_REGISTERED")
        self._actions[action_type] = handler

    def supports(self, action_type: str) -> bool:
        return str(action_type).strip() in self._actions

    def execute(
        self,
        action_type: str,
        *,
        mission_id: str,
        payload: Mapping[str, Any],
        context: Mapping[str, Any],
        idempotency_key: str,
    ) -> ExecutionResult:
        action_type = str(action_type).strip()
        if not self.supports(action_type):
            now = datetime.now(timezone.utc).isoformat()
            return ExecutionResult(
                mission_id=str(mission_id),
                action_type=action_type,
                status="blocked",
                started_at=now,
                completed_at=now,
                idempotency_key=str(idempotency_key),
                verified=False,
                error="unsupported_action",
            )

        started = datetime.now(timezone.utc).isoformat()
        try:
            raw = self._actions[action_type](
                payload=dict(payload or {}),
                context=dict(context or {}),
                mission_id=str(mission_id),
                idempotency_key=str(idempotency_key),
            )
            result = dict(raw or {})
            completed = datetime.now(timezone.utc).isoformat()
            verified = bool(result.get("verified"))
            status = "success" if verified else "blocked"
            return ExecutionResult(
                mission_id=str(mission_id),
                action_type=action_type,
                status=status,
                started_at=started,
                completed_at=completed,
                idempotency_key=str(idempotency_key),
                evidence=result.get("evidence", {}),
                verified=verified,
                error=result.get("error"),
            )
        except Exception as exc:
            completed = datetime.now(timezone.utc).isoformat()
            return ExecutionResult(
                mission_id=str(mission_id),
                action_type=action_type,
                status="blocked",
                started_at=started,
                completed_at=completed,
                idempotency_key=str(idempotency_key),
                verified=False,
                error=type(exc).__name__,
            )


def build_default_registry() -> MissionActionRegistry:
    """Return an empty registry; concrete adapters are registered explicitly.

    Keeping registration explicit prevents mission payloads from selecting
    arbitrary Python callables or shell commands.
    """
    return MissionActionRegistry()
