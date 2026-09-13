from __future__ import annotations

"""Mission lifecycle state management.

Execution is intentionally delegated to core.mission_runtime_authority. This
module may create, assign, preview and complete missions, but it must never
manufacture an execution result.
"""

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json

from core.mission_state import MissionStateNormalizer
from core.mission_lock import MissionLifecycleLock


class MissionLifecycleService:
    """Persist mission lifecycle state without claiming unperformed execution."""

    def __init__(self, root: str = "."):
        self.root = Path(root)
        self.board_path = self.root / "state" / "missions" / "board.json"
        self.manifest_path = self.root / "state" / "takeover" / "manifest.json"
        self.results_dir = self.root / "state" / "missions" / "results"

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def normalize_status(self, status):
        return MissionStateNormalizer.normalize(status)

    def is_completed_status(self, status):
        return MissionStateNormalizer.is_completed(status)

    def is_valid_status(self, status):
        return MissionStateNormalizer.is_valid(status)

    def _load_json(self, path: Path):
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _load_board(self) -> dict:
        data = self._load_json(self.board_path)
        if data is None:
            return {"missions": []}
        if isinstance(data, list):
            return {"missions": data}
        if not isinstance(data, dict):
            raise ValueError("invalid mission board")
        missions = data.get("missions")
        if not isinstance(missions, list):
            raise ValueError("invalid mission board: missions must be a list")
        return data

    def _load_manifest(self) -> dict:
        data = self._load_json(self.manifest_path)
        if data is None:
            return {"agents": {"items": []}}
        if not isinstance(data, dict):
            return {"agents": {"items": []}}
        return data

    def load_state(self):
        return self._load_board(), self._load_manifest()

    def _atomic_write_text(self, path: Path, content: str):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(path)

    def _save_board(self, board: dict) -> None:
        self._atomic_write_text(
            self.board_path,
            json.dumps(board, ensure_ascii=False, indent=2),
        )

    def find_mission(self, board: dict, mission_id: str):
        for mission in board.get("missions", []):
            if isinstance(mission, dict) and str(mission.get("id")) == str(mission_id):
                return mission
        return None

    def find_agent(self, manifest: dict, agent_id: str):
        agents = manifest.get("agents", {}) if isinstance(manifest, dict) else {}
        items = agents.get("items", []) if isinstance(agents, dict) else []
        if isinstance(items, dict):
            items = list(items.values())
        for agent in items:
            if isinstance(agent, dict) and str(agent.get("id")) == str(agent_id):
                return agent
        return None

    def validate_assignment(self, mission, agent):
        return {
            "mission_exists": mission is not None,
            "agent_exists": agent is not None,
            "mission_status_assigned": mission is not None and mission.get("status") == "assigned",
            "assignment_matches": (
                mission is not None and agent is not None
                and str(mission.get("assigned_to")) == str(agent.get("id"))
            ),
            "agent_state_eligible": (
                agent is not None and agent.get("state") in {"idle", "active"}
            ),
        }

    def preview_mission_creation(self, mission_id, description, reward=0):
        board, _ = self.load_state()
        existing = self.find_mission(board, mission_id)
        checks = {
            "mission_does_not_exist": existing is None,
            "mission_id_valid": mission_id is not None and str(mission_id).strip() != "",
            "description_valid": description is not None and str(description).strip() != "",
            "reward_valid": isinstance(reward, (int, float)) and reward >= 0,
        }
        return {
            "status": "ready" if all(checks.values()) else "blocked",
            "mission_id": str(mission_id),
            "description": description,
            "reward": reward,
            "checks": checks,
            "proposed_status": "open" if all(checks.values()) else None,
            "proposed_assigned_to": None,
            "proposed_creation": "create" if all(checks.values()) else None,
            "write_performed": False,
            "read_only": True,
        }

    def create_mission(
        self,
        mission_id: str,
        description: str | None = None,
        reward=0,
        assigned_to: str | None = None,
        action_type: str | None = None,
        action_payload: dict | None = None,
        idempotency_key: str | None = None,
        desc: str | None = None,
        **extra,
    ) -> dict:
        """Create a mission with an explicit executable action contract."""
        if description is None:
            description = desc
        if not mission_id or not description:
            raise ValueError("mission_id and description are required")
        if action_type is None or action_payload is None or idempotency_key is None:
            raise ValueError("action_type, action_payload and idempotency_key are required")
        if not isinstance(action_payload, dict) or not action_payload:
            raise ValueError("action_payload must be a non-empty dict")
        if not isinstance(reward, (int, float)) or reward < 0:
            raise ValueError("reward must be a non-negative number")

        with MissionLifecycleLock(self.root):
            board = self._load_board()
            if self.find_mission(board, mission_id):
                return {
                    "status": "blocked",
                    "reason": "mission_already_exists",
                    "mission_id": str(mission_id),
                    "write_performed": False,
                }
            mission = {
                "id": str(mission_id),
                "desc": str(description),
                "status": "assigned" if assigned_to else "open",
                "assigned_to": str(assigned_to) if assigned_to else None,
                "reward": reward,
                "action_type": str(action_type),
                "action_payload": dict(action_payload),
                "idempotency_key": str(idempotency_key),
                "created_at": self._now(),
                **extra,
            }
            if assigned_to:
                mission["assigned_at"] = mission["created_at"]
            board.setdefault("missions", []).append(mission)
            self._save_board(board)
            return {
                "status": "created",
                "mission_id": str(mission_id),
                "description": str(description),
                "mission_status": mission["status"],
                "assigned_to": mission["assigned_to"],
                "created_at": mission["created_at"],
                "write_performed": True,
                "read_only": False,
            }

    def preview_assignment(self, mission_id, agent_id):
        board, manifest = self.load_state()
        mission = self.find_mission(board, mission_id)
        agent = self.find_agent(manifest, agent_id)
        checks = {
            "mission_exists": mission is not None,
            "mission_is_open": mission is not None and mission.get("status") == "open",
            "mission_is_unassigned": mission is not None and mission.get("assigned_to") is None,
            "agent_exists": agent is not None,
            "agent_is_eligible": agent is not None and agent.get("state") in {"idle", "active"},
        }
        return {
            "status": "ready" if all(checks.values()) else "blocked",
            "mission_id": str(mission_id),
            "agent_id": str(agent_id),
            "mission": mission,
            "agent": agent,
            "checks": checks,
            "proposed_status": "assigned",
            "proposed_assigned_to": str(agent_id),
            "write_performed": False,
            "read_only": True,
        }

    def assign_mission(self, mission_id: str, agent_id: str) -> dict:
        with MissionLifecycleLock(self.root):
            board = self._load_board()
            mission = self.find_mission(board, mission_id)
            if mission is None:
                return {"status": "blocked", "reason": "mission_not_found", "mission_id": str(mission_id), "write_performed": False}
            if not agent_id:
                return {"status": "blocked", "reason": "agent_id_required", "write_performed": False}
            if mission.get("status") != "open" or mission.get("assigned_to") is not None:
                return {"status": "blocked", "reason": "mission_not_assignable", "mission_id": str(mission_id), "write_performed": False}
            manifest = self._load_manifest()
            agent = self.find_agent(manifest, agent_id)
            if agent is None or agent.get("state") not in {"idle", "active"}:
                return {"status": "blocked", "reason": "agent_not_eligible", "mission_id": str(mission_id), "agent_id": str(agent_id), "write_performed": False}
            mission["assigned_to"] = str(agent_id)
            mission["status"] = "assigned"
            mission["assigned_at"] = self._now()
            self._save_board(board)
            return {"status": "assigned", "mission_id": str(mission_id), "agent_id": str(agent_id), "assigned_at": mission["assigned_at"], "write_performed": True, "read_only": False}

    def preview_execution(self, mission_id, agent_id=None):
        board, manifest = self.load_state()
        mission = self.find_mission(board, mission_id)
        if mission is None:
            return {"status": "blocked", "reason": "mission_not_found", "mission_id": str(mission_id), "write_performed": False}
        assigned = mission.get("assigned_to")
        agent = self.find_agent(manifest, assigned)
        checks = {
            "mission_exists": True,
            "agent_exists": agent is not None,
            "mission_status_assigned": mission.get("status") == "assigned",
            "assignment_matches": agent is not None and str(assigned) == str(agent.get("id")),
            "agent_state_eligible": agent is not None and agent.get("state") in {"idle", "active"},
            "action_contract_present": bool(mission.get("action_type")) and isinstance(mission.get("action_payload"), dict) and bool(mission.get("idempotency_key")),
        }
        if agent_id is not None:
            checks["requested_agent_matches"] = str(agent_id) == str(assigned)
        return {
            "status": "ready" if all(checks.values()) else "blocked",
            "mission_id": str(mission_id),
            "description": mission.get("desc"),
            "agent_id": assigned,
            "current_status": mission.get("status"),
            "proposed_status": "executed" if all(checks.values()) else None,
            "mission": mission,
            "agent": agent,
            "checks": checks,
            "proposed_execution": "execute" if all(checks.values()) else None,
            "write_performed": False,
            "read_only": True,
        }

    def preview_completion(self, mission_id):
        board, manifest = self.load_state()
        mission = self.find_mission(board, mission_id)
        if mission is None:
            return {"status": "blocked", "reason": "mission_not_found", "mission_id": str(mission_id), "write_performed": False}
        result_path = mission.get("result_file")
        result = None
        if result_path:
            path = self.root / result_path
            if path.exists():
                try:
                    result = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    result = None
        checks = {
            "mission_exists": True,
            "mission_status_executed": MissionStateNormalizer.normalize(mission.get("status")) == "executed",
            "result_exists": result is not None,
            "result_success": result is not None and result.get("execution_status") == "success",
            "result_verified": result is not None and result.get("verified") is True,
            "completion_pending": result is not None and result.get("mission_completion") == "pending",
            "result_hash_valid": self._result_hash_valid(result),
        }
        return {
            "status": "ready" if all(checks.values()) else "blocked",
            "mission_id": str(mission_id),
            "mission": mission,
            "agent": self.find_agent(manifest, mission.get("assigned_to")),
            "result": result,
            "checks": checks,
            "proposed_status": "completed" if all(checks.values()) else None,
            "write_performed": False,
            "read_only": True,
        }

    @staticmethod
    def _result_hash_valid(result) -> bool:
        if not isinstance(result, dict):
            return False
        stored_hash = result.get("result_sha256")
        if not stored_hash:
            return False
        canonical_result = dict(result)
        canonical_result.pop("result_sha256", None)
        canonical = json.dumps(canonical_result, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest() == stored_hash

    def execute_mission(self, *args, **kwargs) -> dict:
        """Retired: execution must go through Mission Runtime Authority."""
        raise RuntimeError("MissionLifecycleService.execute_mission is retired; use execute_mission_authority")

    def complete_mission(self, mission_id: str, agent_id: str | None = None) -> dict:
        with MissionLifecycleLock(self.root):
            board = self._load_board()
            mission = self.find_mission(board, mission_id)
            if mission is None:
                return {"status": "blocked", "reason": "mission_not_found", "mission_id": str(mission_id), "write_performed": False}
            if MissionStateNormalizer.normalize(mission.get("status")) == "completed":
                return {"status": "completed", "reason": "mission_already_completed", "mission_id": str(mission_id), "write_performed": False, "read_only": True}
            if MissionStateNormalizer.normalize(mission.get("status")) != "executed":
                return {"status": "blocked", "reason": "mission_must_be_executed", "mission_id": str(mission_id), "write_performed": False}
            if agent_id is not None and str(mission.get("assigned_to")) != str(agent_id):
                return {"status": "blocked", "reason": "agent_mismatch", "mission_id": str(mission_id), "write_performed": False}
            result_ref = mission.get("result_file")
            if not result_ref:
                return {"status": "blocked", "reason": "verified_execution_result_is_missing", "mission_id": str(mission_id), "write_performed": False}
            result_path = self.root / result_ref
            if not result_path.exists():
                return {"status": "blocked", "reason": "verified_execution_result_file_is_missing", "mission_id": str(mission_id), "write_performed": False}
            try:
                result = json.loads(result_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return {"status": "blocked", "reason": "invalid_execution_result", "mission_id": str(mission_id), "write_performed": False}
            if result.get("execution_status") != "success" or result.get("verified") is not True:
                return {"status": "blocked", "reason": "execution_result_not_verified", "mission_id": str(mission_id), "write_performed": False}
            if result.get("mission_completion") != "pending":
                return {"status": "blocked", "reason": "execution_result_not_pending", "mission_id": str(mission_id), "write_performed": False}
            if not self._result_hash_valid(result):
                return {"status": "blocked", "reason": "execution_result_integrity_failed", "mission_id": str(mission_id), "write_performed": False}
            expected_sha = mission.get("execution_result_sha256")
            if expected_sha and expected_sha != result.get("result_sha256"):
                return {"status": "blocked", "reason": "mission_result_hash_mismatch", "mission_id": str(mission_id), "write_performed": False}

            completed_at = self._now()
            result["mission_completion"] = "completed"
            result["completed_at"] = completed_at
            result.pop("result_sha256", None)
            canonical = json.dumps(result, sort_keys=True, ensure_ascii=False)
            result["result_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            self._atomic_write_text(
                result_path,
                json.dumps(result, indent=2, ensure_ascii=False),
            )
            mission["status"] = "completed"
            mission["completed_at"] = completed_at
            mission["mission_completion"] = "completed"
            mission["execution_result_sha256"] = result["result_sha256"]
            self._save_board(board)
            return {
                "status": "completed",
                "mission_id": str(mission_id),
                "agent_id": mission.get("assigned_to"),
                "completed_at": completed_at,
                "result_path": str(result_path),
                "result_sha256": result["result_sha256"],
                "write_performed": True,
                "read_only": False,
            }
