import pytest

from core.mission_lifecycle import MissionLifecycleService


def test_create_mission_requires_explicit_action_contract(tmp_path):
    service = MissionLifecycleService(str(tmp_path))
    with pytest.raises(ValueError, match="action_type"):
        service.create_mission("m1", "test mission")


def test_create_mission_persists_action_contract(tmp_path):
    service = MissionLifecycleService(str(tmp_path))
    mission = service.create_mission(
        "m1",
        "complete academy stage",
        assigned_to="agent1",
        action_type="academy.complete_stage",
        action_payload={"course_id": "bitcoin_mastery", "stage": 1},
        idempotency_key="mission:m1:academy:bitcoin_mastery:1",
    )
    assert mission["status"] == "assigned"
    assert mission["action_type"] == "academy.complete_stage"
    assert mission["action_payload"]["stage"] == 1
    assert mission["idempotency_key"].startswith("mission:m1:")
