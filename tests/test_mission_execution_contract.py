import inspect
import json

from agents.mission_executor import MissionExecutorAgent
from core.kernel import SLHKernel
from core.mission_action_registry import MissionActionRegistry
from core.mission_orchestrator import MissionOrchestrator
from core.mission_runtime_authority import execute_mission_authority
from core.runtime import Runtime


def _write_state(tmp_path, mission, agent):
    board_path = tmp_path / "state" / "missions" / "board.json"
    manifest_path = tmp_path / "state" / "takeover" / "manifest.json"
    board_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    board_path.write_text(json.dumps({"missions": [mission]}), encoding="utf-8")
    manifest_path.write_text(json.dumps({"agents": {"items": [agent]}}), encoding="utf-8")


def test_runtime_boundary_contains_no_generic_executor():
    executor_source = inspect.getsource(MissionExecutorAgent)
    orchestrator_source = inspect.getsource(MissionOrchestrator)
    assert "subprocess" not in executor_source
    assert "os.system" not in executor_source
    assert "eval(" not in executor_source
    assert "exec(" not in executor_source
    assert "MissionExecutorAgent(" not in orchestrator_source


def test_unsupported_capability_is_blocked():
    result = MissionExecutorAgent().process({"cmd": "Mission Executor:execute_mission", "mission_id": "m1", "capability": "shell", "action": "exec"})
    assert result["execution_status"] == "blocked"
    assert result["reason"] == "unsupported_capability_or_action"


def test_missing_action_contract_is_blocked():
    result = MissionExecutorAgent().process({"cmd": "Mission Executor:execute_mission", "mission_id": "m1", "capability": "mission_execution", "action": "execute_mission"})
    assert result["execution_status"] == "blocked"
    assert result["reason"] == "mission_execution_contract_missing"


def test_registry_rejects_arbitrary_action():
    registry = MissionActionRegistry()
    result = registry.execute("shell.exec", mission_id="m1", payload={}, context={}, idempotency_key="mission:m1:1")
    assert result.status == "blocked"
    assert result.error == "unsupported_action"


def test_registry_requires_verified_evidence():
    registry = MissionActionRegistry()
    registry.register("fake.action", lambda **kwargs: {"verified": True, "evidence": {}})
    result = registry.execute("fake.action", mission_id="m1", payload={}, context={}, idempotency_key="mission:m1:1")
    assert result.status == "blocked"
    assert result.verified is False


def _runtime_fixture(tmp_path, monkeypatch):
    mission = {"id": "m-runtime-1", "desc": "bounded academy action", "status": "assigned", "assigned_to": "agent-1", "reward": 0, "action_type": "academy.complete_stage", "action_payload": {"course_id": "bitcoin_mastery", "stage": 1}, "idempotency_key": "mission:m-runtime-1:academy:1"}
    agent = {"id": "agent-1", "name": "Mission Executor", "state": "idle", "runtime_class": "MissionExecutorAgent", "owner_id": "owner-1"}
    _write_state(tmp_path, mission, agent)
    import state_manager
    from core import academy_manager
    monkeypatch.setattr(state_manager, "get_agents", lambda: {"agent-1": agent})
    calls = []
    monkeypatch.setattr(academy_manager, "complete_stage", lambda uid, course_id, stage: calls.append((uid, course_id, stage)) or {"ok": True, "uid": uid, "course_id": course_id, "stage": stage})
    kernel = SLHKernel()
    kernel.register("Mission Executor", MissionExecutorAgent())
    return mission, Runtime(kernel), calls


def test_authority_uses_kernel_runtime_and_commits_verified_result(tmp_path, monkeypatch):
    mission, runtime, calls = _runtime_fixture(tmp_path, monkeypatch)
    result = execute_mission_authority("m-runtime-1", root=tmp_path, runtime=runtime)
    assert result["status"] == "executed"
    data = result["runtime_result"]["data"]
    assert data["execution_status"] == "success"
    assert data["verified"] is True
    assert data["action_type"] == "academy.complete_stage"
    assert data["idempotency_key"] == mission["idempotency_key"]
    assert data["evidence"]["uid"] == "owner-1"
    assert calls == [("owner-1", "bitcoin_mastery", 1)]
    board = json.loads((tmp_path / "state" / "missions" / "board.json").read_text(encoding="utf-8"))
    assert board["missions"][0]["status"] == "executed"
    result_path = tmp_path / result["lifecycle_result"]["result_path"]
    assert result_path.exists()
    persisted = json.loads(result_path.read_text(encoding="utf-8"))
    assert persisted["result_sha256"]


def test_repeated_execution_does_not_repeat_action(tmp_path, monkeypatch):
    _mission, runtime, calls = _runtime_fixture(tmp_path, monkeypatch)
    first = execute_mission_authority("m-runtime-1", root=tmp_path, runtime=runtime)
    second = execute_mission_authority("m-runtime-1", root=tmp_path, runtime=runtime)
    assert first["status"] == "executed"
    assert second["status"] == "blocked"
    assert second["reason"] == "mission_not_executable"
    assert len(calls) == 1


def test_authority_blocks_without_contract_before_runtime(tmp_path, monkeypatch):
    mission = {"id": "m-block-1", "desc": "legacy mission", "status": "assigned", "assigned_to": "agent-1", "reward": 0}
    agent = {"id": "agent-1", "name": "Mission Executor", "state": "idle", "runtime_class": "MissionExecutorAgent", "owner_id": "owner-1"}
    _write_state(tmp_path, mission, agent)
    import state_manager
    monkeypatch.setattr(state_manager, "get_agents", lambda: {"agent-1": agent})

    class ExplodingRuntime:
        def execute(self, event):
            raise AssertionError("runtime must not be called")

    result = execute_mission_authority("m-block-1", root=tmp_path, runtime=ExplodingRuntime())
    assert result["status"] == "blocked"
    assert result["reason"] == "mission_execution_contract_missing"


def test_orchestrator_routes_execute_to_authority(tmp_path, monkeypatch):
    mission = {"id": "m-orch-1", "desc": "runtime routed mission", "status": "assigned", "assigned_to": "agent-1", "reward": 0, "action_type": "academy.complete_stage", "action_payload": {"course_id": "bitcoin_mastery", "stage": 1}, "idempotency_key": "mission:m-orch-1:1"}
    agent = {"id": "agent-1", "name": "Mission Executor", "state": "idle", "runtime_class": "MissionExecutorAgent", "owner_id": "owner-1"}
    _write_state(tmp_path, mission, agent)
    calls = []
    import core.mission_orchestrator as orchestrator_module
    monkeypatch.setattr(orchestrator_module, "execute_mission_authority", lambda **kwargs: calls.append(kwargs) or {"status": "executed", "mission_id": "m-orch-1"})
    result = MissionOrchestrator(tmp_path).run_next_action("m-orch-1", "agent-1")
    assert result["status"] == "executed"
    assert result["action"] == "execute"
    assert calls == [{"mission_id": "m-orch-1", "root": tmp_path}]
