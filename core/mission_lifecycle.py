from __future__ import annotations

# Mission execution is intentionally delegated to core.mission_runtime_authority.
# This module retains lifecycle/state transitions only; it must never manufacture
# an execution result. The legacy execute_mission() entry point is retired.

from pathlib import Path
import hashlib
import json
from datetime import datetime, timezone

from core.mission_state import normalize_status


class MissionLifecycleService:
    """Persist mission lifecycle state without claiming unperformed execution."""

    def __init__(self, root: str = "."):
        self.root = Path(root)
        self.board_path = self.root / "state" / "missions" / "board.json"
        self.results_dir = self.root / "state" / "missions" / "results"

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _load_board(self) -> dict:
        if not self.board_path.exists():
            return {"missions": []}
        data = json.loads(self.board_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return {"missions": data}
        return data

    def _save_board(self, board: dict) -> None:
        self.board_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.board_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.board_path)

    def _find(self, board: dict, mission_id: str) -> dict | None:
        for mission in board.get("missions", []):
            if str(mission.get("id")) == str(mission_id):
                return mission
        return None

    def create_mission(self, mission_id: str, desc: str, assigned_to: str | None = None,
                       action_type: str | None = None, action_payload: dict | None = None,
                       idempotency_key: str | None = None, **extra) -> dict:
        """Create a mission; executable missions require an explicit action contract."""
        if not mission_id or not desc:
            raise ValueError("mission_id and desc are required")
        if action_type is None or action_payload is None or idempotency_key is None:
            raise ValueError("action_type, action_payload and idempotency_key are required")
        if not isinstance(action_payload, dict) or not action_payload:
            raise ValueError("action_payload must be a non-empty dict")

        board = self._load_board()
        if self._find(board, mission_id):
            raise ValueError(f"mission already exists: {mission_id}")

        mission = {
            "id": str(mission_id),
            "desc": str(desc),
            "status": "assigned" if assigned_to else "open",
            "assigned_to": assigned_to,
            "action_type": str(action_type),
            "action_payload": action_payload,
            "idempotency_key": str(idempotency_key),
            "created_at": self._now(),
            **extra,
        }
        board.setdefault("missions", []).append(mission)
        self._save_board(board)
        return mission

    def assign_mission(self, mission_id: str, agent_id: str) -> dict:
        board = self._load_board()
        mission = self._find(board, mission_id)
        if not mission:
            raise ValueError(f"mission not found: {mission_id}")
        if not agent_id:
            raise ValueError("agent_id is required")
        status = normalize_status(mission.get("status"))
        if status not in {"open", "assigned"}:
            raise ValueError(f"mission cannot be assigned from status {status}")
        mission["assigned_to"] = agent_id
        mission["status"] = "assigned"
        mission["assigned_at"] = self._now()
        self._save_board(board)
        return mission

    def preview_execution(self, mission_id: str, agent_id: str | None = None) -> dict:
        board = self._load_board()
        mission = self._find(board, mission_id)
        if not mission:
            return {"ok": False, "reason": "mission_not_found"}
        status = normalize_status(mission.get("status"))
        if status != "assigned":
            return {"ok": False, "reason": f"invalid_status:{status}"}
        if not mission.get("assigned_to"):
            return {"ok": False, "reason": "unassigned"}
        if agent_id is not None and str(mission.get("assigned_to")) != str(agent_id):
            return {"ok": False, "reason": "agent_mismatch"}
        if not mission.get("action_type") or not isinstance(mission.get("action_payload"), dict):
            return {"ok": False, "reason": "missing_action_contract"}
        if not mission.get("idempotency_key"):
            return {"ok": False, "reason": "missing_idempotency_key"}
        return {"ok": True, "mission": mission}

    def execute_mission(self, *args, **kwargs) -> dict:
        """Retired: execution must go through Mission Runtime Authority."""
        raise RuntimeError("MissionLifecycleService.execute_mission is retired; use execute_mission_authority")

    def complete_mission(self, mission_id: str, agent_id: str | None = None) -> dict:
        board = self._load_board()
        mission = self._find(board, mission_id)
        if not mission:
            raise ValueError(f"mission not found: {mission_id}")
        if normalize_status(mission.get("status")) != "executed":
            raise ValueError("mission must have a verified executed result before completion")
        if agent_id is not None and str(mission.get("assigned_to")) != str(agent_id):
            raise ValueError("agent mismatch")

        result_ref = mission.get("result_file")
        if not result_ref:
            raise ValueError("verified execution result is missing")
        result_path = self.root / result_ref
        if not result_path.exists():
            raise ValueError("verified execution result file is missing")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        if result.get("execution_status") != "success" or result.get("verified") is not True:
            raise ValueError("execution result is not verified")
        expected_sha = mission.get("execution_result_sha256")
        actual_sha = hashlib.sha256(result_path.read_bytes()).hexdigest()
        if expected_sha and expected_sha != actual_sha:
            raise ValueError("execution result integrity check failed")
        mission["status"] = "completed"
        mission["completed_at"] = self._now()
        mission["mission_completion"] = "completed"
        self._save_board(board)
        return mission
