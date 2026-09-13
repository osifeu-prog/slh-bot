import pytest

from core.mission_lifecycle import MissionLifecycleService


def test_legacy_execute_mission_is_retired(tmp_path):
    service = MissionLifecycleService(str(tmp_path))
    with pytest.raises(RuntimeError, match="retired"):
        service.execute_mission("m1", "agent1")
