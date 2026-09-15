from agents.mission_executor import MissionExecutorAgent


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
