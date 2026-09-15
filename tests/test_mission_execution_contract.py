import json

from core.mission_lifecycle import MissionLifecycleService


def _write_state(root):
    board = {
        "missions": [
            {
                "id": "TEST-EXEC-1",
                "desc": "bounded execution contract test",
                "status": "assigned",
                "assigned_to": "agent-1",
                "reward": 0,
            }
        ]
    }
    manifest = {
        "agents": [
            {
                "id": "agent-1",
                "name": "Mission Executor",
                "state": "idle",
                "runtime_class": "MissionExecutorAgent",
            }
        ]
    }
    board_path = root / "state" / "missions" / "board.json"
    manifest_path = root / "state" / "takeover" / "manifest.json"
    board_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    board_path.write_text(json.dumps(board), encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def test_execute_requires_real_result(tmp_path):
    _write_state(tmp_path)
    service = MissionLifecycleService(tmp_path)

    result = service.execute_mission("TEST-EXEC-1")

    assert result["status"] == "blocked"
    assert result["reason"] == "execution_result_required"

    board = json.loads(
        (tmp_path / "state" / "missions" / "board.json").read_text(
            encoding="utf-8"
        )
    )
    assert board["missions"][0]["status"] == "assigned"


def test_completion_rejects_synthetic_success(tmp_path):
    _write_state(tmp_path)
    service = MissionLifecycleService(tmp_path)

    result = service.execute_mission(
        "TEST-EXEC-1",
        execution_result={
            "execution_status": "success",
            "verified": True,
            "mission_id": "TEST-EXEC-1",
            "result": {},
        },
    )

    assert result["status"] == "executed"

    completion = service.complete_mission("TEST-EXEC-1")
    assert completion["status"] == "completed"
