import json

from core.kernel import SLHKernel
from core.runtime import Runtime
from core.mission_runtime_authority import execute_mission_authority
from agents.mission_executor import MissionExecutorAgent


def test_allowlisted_academy_mission_runs_end_to_end_in_isolated_state(tmp_path, monkeypatch):
    """Prove the full non-production execution path with real Academy mutation."""
    state_dir = tmp_path / "state"
    missions_dir = state_dir / "missions"
    results_dir = missions_dir / "results"
    missions_dir.mkdir(parents=True)
    results_dir.mkdir(parents=True)

    db_path = state_dir / "db.json"
    reward_ledger = state_dir / "rewards_ledger.json"
    courses_path = tmp_path / "courses.json"

    db = {
        "users": {
            "u1": {
                "name": "Test User",
                "wallet": {"credits": 0},
                "academy": {
                    "active_course": "bitcoin_mastery",
                    "courses": {
                        "bitcoin_mastery": {"stage": 0, "completed": []}
                    },
                },
                "gamification": {"points": 0, "level": 1},
            }
        },
        "agents": {
            "agent-1": {
                "id": "agent-1",
                "name": "MissionAgent",
                "state": "idle",
                "runtime_class": "MissionExecutorAgent",
                "owner_id": "u1",
            }
        },
    }
    db_path.write_text(json.dumps(db), encoding="utf-8")
    courses_path.write_text(
        json.dumps(
            {
                "bitcoin_mastery": {
                    "title": "Test course",
                    "stages": [{"id": 1, "name": "Stage 1", "lesson": "unused"}],
                }
            }
        ),
        encoding="utf-8",
    )

    mission = {
        "id": "m-e2e-1",
        "desc": "Complete Academy stage 1",
        "status": "assigned",
        "assigned_to": "agent-1",
        "reward": 0,
        "action_type": "academy.complete_stage",
        "action_payload": {"course_id": "bitcoin_mastery", "stage": 1},
        "idempotency_key": "mission:m-e2e-1:academy:1",
    }
    (missions_dir / "board.json").write_text(
        json.dumps({"missions": [mission]}), encoding="utf-8"
    )
    (tmp_path / "state" / "takeover").mkdir(parents=True)
    (tmp_path / "state" / "takeover" / "manifest.json").write_text(
        json.dumps({"agents": {"items": [{"id": "agent-1", "name": "MissionAgent", "state": "idle", "runtime_class": "MissionExecutorAgent"}]}}),
        encoding="utf-8",
    )

    import state_manager
    from core import profile_manager, academy_manager, reward_engine
    import agents.mission_executor as mission_executor

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(state_manager, "DB_FILE", str(db_path))
    monkeypatch.setattr(state_manager, "_LOCK_PATH", str(db_path) + ".lock")
    monkeypatch.setattr(profile_manager, "DB_PATH", str(db_path))
    monkeypatch.setattr(academy_manager, "COURSE_FILE", str(courses_path))
    monkeypatch.setattr(reward_engine, "LEDGER", reward_ledger)
    monkeypatch.setattr(
        mission_executor.state_manager,
        "get_agents",
        lambda: db["agents"],
    )

    kernel = SLHKernel()
    kernel.register("MissionAgent", MissionExecutorAgent())
    runtime = Runtime(kernel)

    result = execute_mission_authority(
        mission_id="m-e2e-1",
        root=str(tmp_path),
        runtime=runtime,
    )

    assert result["status"] == "completed"
    assert result["runtime_result"]["type"] == "agent"
    assert result["runtime_result"]["data"]["verified"] is True
    assert result["persistence"]["status"] == "executed"
    assert result["completion"]["status"] == "completed"

    final_db = json.loads(db_path.read_text(encoding="utf-8"))
    user = final_db["users"]["u1"]
    assert user["academy"]["courses"]["bitcoin_mastery"]["stage"] == 1
    assert user["academy"]["courses"]["bitcoin_mastery"]["completed"] == [1]
    assert user["gamification"]["points"] == 25

    board = json.loads((missions_dir / "board.json").read_text(encoding="utf-8"))
    assert board["missions"][0]["status"] == "completed"
    result_file = tmp_path / board["missions"][0]["result_file"]
    persisted = json.loads(result_file.read_text(encoding="utf-8"))
    assert persisted["verified"] is True
    assert persisted["mission_completion"] == "completed"
