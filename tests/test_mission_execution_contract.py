from agents.mission_executor import MissionExecutorAgent
from core.mission_lifecycle import MissionLifecycleService
from core.mission_orchestrator import MissionOrchestrator


def test_execute_requires_real_result():
    agent = MissionExecutorAgent()
    result = agent.process({"cmd": "Mission Executor:execute_mission", "mission_id": "TEST-EXEC-1"})
    assert result["execution_status"] == "blocked"
    assert result["reason"] == "execution_result_required"
