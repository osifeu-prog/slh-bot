"""Canonical allowlisted mission execution authority.

Mission execution is deliberately narrow: missions must declare an explicit
allowlisted action and an idempotency key. The first supported action is the
existing Academy authority.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from core.academy_manager import complete_stage
from core.mission_action_registry import MissionActionRegistry
from core.mission_lock import MissionLifecycleLock


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _academy_complete_stage(*, payload, context, mission_id, idempotency_key):
    uid = context.get("owner_id")
    if uid is None:
        return {"verified": False, "error": "trusted_owner_missing", "evidence": {}}

    course_id = payload.get("course_id")
    stage = payload.get("stage")
    if not course_id or stage is None:
        return {"verified": False, "error": "invalid_academy_payload", "evidence": {}}

    result = complete_stage(str(uid), str(course_id), stage)
    if not isinstance(result, dict) or not result.get("ok"):
        return {"verified": False, "error": result.get("error", "academy_action_failed"), "evidence": {"academy_result": result}}

    return {
        "verified": True,
        "evidence": {
            "authority": "core.academy_manager.complete_stage",
            "owner_id": str(uid),
            "course_id": str(course_id),
            "stage": int(stage),
            "academy_result": result,
            "idempotency_key": str(idempotency_key),
        },
    }


def build_registry() -> MissionActionRegistry:
    registry = MissionActionRegistry()
    registry.register("academy.complete_stage", _academy_complete_stage)
    return registry


def execute_mission(mission: Dict[str, Any], agent: Dict[str, Any], root: str = ".") -> Dict[str, Any]:
    mission_id = str(mission.get("id", ""))
    action_type = str(mission.get("action_type", "")).strip()
    payload = mission.get("action_payload") or {}
    idempotency_key = str(mission.get("idempotency_key", "")).strip()

    if not mission_id or not action_type or not idempotency_key or not isinstance(payload, dict):
        return {"status": "blocked", "mission_id": mission_id, "reason": "mission_execution_contract_missing"}

    owner_id = agent.get("owner_id")
    if owner_id is None:
        return {"status": "blocked", "mission_id": mission_id, "reason": "trusted_agent_owner_missing"}

    registry = build_registry()
    result = registry.execute(
        action_type,
        mission_id=mission_id,
        payload=payload,
        context={"owner_id": str(owner_id), "agent_id": str(agent.get("id", ""))},
        idempotency_key=idempotency_key,
    )

    if result.status != "success" or not result.verified:
        return {"status": "blocked", "mission_id": mission_id, "execution_result": result.as_dict()}

    root_path = Path(root)
    board_path = root_path / "state" / "missions" / "board.json"
    results_dir = root_path / "state" / "missions" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    with MissionLifecycleLock(root):
        board = json.loads(board_path.read_text(encoding="utf-8"))
        target = next((item for item in board.get("missions", []) if str(item.get("id")) == mission_id), None)
        if target is None:
            return {"status": "blocked", "mission_id": mission_id, "reason": "mission_not_found"}
        if target.get("status") not in ("assigned", "executed"):
            return {"status": "blocked", "mission_id": mission_id, "reason": "mission_not_assigned"}

        target["status"] = "executed"
        target["execution_started_at"] = result.started_at
        target["execution_completed_at"] = result.completed_at
        target["execution_action_type"] = action_type
        target["execution_idempotency_key"] = idempotency_key

        recorded = {
            "result_id": f"mission-{mission_id}-{idempotency_key}",
            "mission_id": mission_id,
            "agent_id": str(agent.get("id", "")),
            "action_type": action_type,
            "execution_status": "success",
            "verified": True,
            "mission_completion": "pending",
            "idempotency_key": idempotency_key,
            "evidence": dict(result.evidence),
            "recorded_at": result.completed_at,
        }
        canonical = json.dumps(recorded, sort_keys=True, ensure_ascii=False)
        recorded["result_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        result_path = results_dir / f"{recorded['result_id']}.json"
        result_path.write_text(json.dumps(recorded, indent=2, ensure_ascii=False), encoding="utf-8")
        board_path.write_text(json.dumps(board, indent=2, ensure_ascii=False), encoding="utf-8")

    return {"status": "executed", "mission_id": mission_id, "execution_result": result.as_dict(), "recorded_result": recorded}
