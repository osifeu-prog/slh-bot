from agents.mission_executor import MissionExecutorAgent
from core.mission_lifecycle import MissionLifecycleService
from core.mission_orchestrator import MissionOrchestrator


def test_execute_requires_real_result():
    agent = MissionExecutorAgent()

    result = agent.process(
        {
            "cmd": "Mission Executor:execute_mission",
            "mission_id": "TEST-EXEC-1",
        }
    )

    assert result["execution_status"] == "blocked"
    assert result["reason"] == "execution_result_required"


def test_execute_requires_verified_evidence():
    agent = MissionExecutorAgent()

    result = agent.process(
        {
            "cmd": "Mission Executor:execute_mission",
            "mission_id": "TEST-EXEC-1",
            "execution_result": {
                "execution_status": "success",
                "verified": True,
            },
        }
    )

    assert result["execution_status"] == "blocked"
    assert result["reason"] == "execution_evidence_required"


def test_verified_result_is_passed_through():
    agent = MissionExecutorAgent()

    execution_result = {
        "execution_status": "success",
        "verified": True,
        "evidence": {"check": "passed"},
    }

    result = agent.process(
        {
            "cmd": "Mission Executor:execute_mission",
            "mission_id": "TEST-EXEC-1",
            "source": "test",
            "execution_result": execution_result,
        }
    )

    assert result["execution_status"] == "success"
    assert result["verified"] is True
    assert result["evidence"] == {"check": "passed"}
    assert result["mission_id"] == "TEST-EXEC-1"
    assert result["mission_completion"] == "pending"


def test_lifecycle_requires_execution_result(tmp_path):
    board = {
        "missions": [{
            "id": "TEST-EXEC-1",
            "desc": "bounded execution contract test",
            "status": "assigned",
            "assigned_to": "agent-1",
            "reward": 0,
        }]
    }
    manifest = {"agents": {"items": [{
        "id": "agent-1",
        "name": "Mission Executor",
        "state": "idle",
        "runtime_class": "MissionExecutorAgent",
    }]}}
    board_path = tmp_path / "state" / "missions" / "board.json"
    manifest_path = tmp_path / "state" / "takeover" / "manifest.json"
    board_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    board_path.write_text(__import__("json").dumps(board), encoding="utf-8")
    manifest_path.write_text(__import__("json").dumps(manifest), encoding="utf-8")

    result = MissionLifecycleService(tmp_path).execute_mission("TEST-EXEC-1")

    assert result["status"] == "blocked"
    assert result["reason"] == "execution_result_required"


def test_lifecycle_accepts_only_verified_execution_result(tmp_path):
    import json

    board = {"missions": [{
        "id": "TEST-EXEC-2",
        "desc": "bounded execution contract test",
        "status": "assigned",
        "assigned_to": "agent-1",
        "reward": 0,
    }]}
    manifest = {"agents": {"items": [{
        "id": "agent-1",
        "name": "Mission Executor",
        "state": "idle",
        "runtime_class": "MissionExecutorAgent",
    }]}}
    board_path = tmp_path / "state" / "missions" / "board.json"
    manifest_path = tmp_path / "state" / "takeover" / "manifest.json"
    board_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    board_path.write_text(json.dumps(board), encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    service = MissionLifecycleService(tmp_path)
    result = service.execute_mission(
        "TEST-EXEC-2",
        execution_result={
            "execution_status": "success",
            "verified": True,
            "evidence": {"check": "passed"},
        },
    )

    assert result["status"] == "executed"
    assert result["execution_status"] == "success"
    assert result["result_id"]


def test_orchestrator_execute_requires_runtime_result(tmp_path):
    import json

    board = {"missions": [{
        "id": "TEST-ORCH-1",
        "desc": "orchestrator execution contract test",
        "status": "assigned",
        "assigned_to": "agent-1",
        "reward": 0,
    }]}
    manifest = {"agents": {"items": [{
        "id": "agent-1",
        "name": "Mission Executor",
        "state": "idle",
        "runtime_class": "MissionExecutorAgent",
    }]}}
    board_path = tmp_path / "state" / "missions" / "board.json"
    manifest_path = tmp_path / "state" / "takeover" / "manifest.json"
    board_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    board_path.write_text(json.dumps(board), encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    orchestrator = MissionOrchestrator(tmp_path)
    result = orchestrator.run_next_action(
        mission_id="TEST-ORCH-1",
        agent_id="agent-1",
    )

    assert result["status"] == "blocked"
    assert result["action"] == "execute"
    assert result["result"]["reason"] == "execution_result_required"
