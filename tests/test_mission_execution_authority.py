from core.mission_action_registry import MissionActionRegistry
from core.mission_action_adapters import execute_academy_complete_stage


def test_unsupported_action_is_blocked():
    registry = MissionActionRegistry()
    result = registry.execute(
        "not.allowed",
        mission_id="m1",
        payload={},
        context={},
        idempotency_key="mission:m1:execute",
    )
    assert result.status == "blocked"
    assert result.verified is False
    assert result.error == "unsupported_action"


def test_registry_requires_verified_adapter_result():
    registry = MissionActionRegistry()
    registry.register(
        "test.action",
        lambda **kwargs: {"verified": False, "evidence": {"ran": True}},
    )
    result = registry.execute(
        "test.action",
        mission_id="m1",
        payload={},
        context={},
        idempotency_key="mission:m1:execute",
    )
    assert result.status == "blocked"
    assert result.verified is False


def test_academy_adapter_rejects_missing_trusted_owner():
    result = execute_academy_complete_stage(
        payload={"course_id": "bitcoin_mastery", "stage": 1},
        context={},
        mission_id="m1",
        idempotency_key="mission:m1:execute",
    )
    assert result["verified"] is False
    assert result["error"] == "missing_trusted_owner"


def test_academy_adapter_rejects_incomplete_payload():
    result = execute_academy_complete_stage(
        payload={"course_id": "bitcoin_mastery"},
        context={"owner_id": "123"},
        mission_id="m1",
        idempotency_key="mission:m1:execute",
    )
    assert result["verified"] is False
    assert result["error"] == "invalid_academy_payload"
