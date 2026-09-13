"""Persistence boundary for verified mission execution results.

This module records a result produced by the canonical Mission Runtime. It
never creates a successful execution result on its own and never performs a
mission action.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def persist_verified_execution(mission_id, execution_result, root="."):
    """Persist an already-verified Runtime result and move the mission to executed.

    The caller must provide a structured, successful, verified result with an
    action type, idempotency key and evidence. No action is performed here.
    """
    if not isinstance(execution_result, dict):
        return {"status": "blocked", "reason": "execution_result_invalid"}

    required = ("mission_id", "action_type", "idempotency_key", "evidence")
    missing = [key for key in required if not execution_result.get(key)]
    if missing:
        return {"status": "blocked", "reason": "execution_result_contract_missing", "missing": missing}

    if execution_result.get("execution_status") != "success" or execution_result.get("verified") is not True:
        return {"status": "blocked", "reason": "execution_result_not_verified"}

    if str(execution_result.get("mission_id")) != str(mission_id):
        return {"status": "blocked", "reason": "mission_id_mismatch"}

    root = Path(root)
    board_path = root / "state" / "missions" / "board.json"
    results_dir = root / "state" / "missions" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    try:
        board = json.loads(board_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "blocked", "reason": "board_unreadable", "error": type(exc).__name__}

    mission = next((m for m in board.get("missions", []) if str(m.get("id")) == str(mission_id)), None)
    if mission is None:
        return {"status": "blocked", "reason": "mission_not_found", "mission_id": str(mission_id)}
    if mission.get("status") != "assigned":
        return {"status": "blocked", "reason": "mission_not_assigned", "current_status": mission.get("status")}

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    result_id = f"mission-{mission_id}-{timestamp}"
    completed_at = execution_result.get("completed_at") or datetime.now(timezone.utc).isoformat()

    result = dict(execution_result)
    result["result_id"] = result_id
    result["recorded_at"] = completed_at
    result["mission_completion"] = "pending"

    canonical = json.dumps(result, sort_keys=True, ensure_ascii=False)
    result["result_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    result_path = results_dir / f"{result_id}.json"
    result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    mission["status"] = "executed"
    mission["execution_started_at"] = execution_result.get("started_at") or completed_at
    mission["execution_completed_at"] = completed_at
    board_path.write_text(json.dumps(board, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "status": "executed",
        "mission_id": str(mission_id),
        "result_id": result_id,
        "result_path": str(result_path),
        "action_type": execution_result.get("action_type"),
        "idempotency_key": execution_result.get("idempotency_key"),
        "verified": True,
        "write_performed": True,
    }
