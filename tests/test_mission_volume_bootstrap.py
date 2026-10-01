import json

from core.mission_lifecycle import MissionLifecycleService


def test_create_mission_bootstraps_missing_volume_state(tmp_path, monkeypatch):
    import state_manager

    agent = {"id": "agent-1", "name": "Mission Executor", "state": "idle"}
    monkeypatch.setattr(state_manager, "get_agents", lambda: {"agent-1": agent})

    service = MissionLifecycleService(tmp_path)
    result = service.create_mission("m1", "bootstrap test")

    assert result["status"] == "created"
    board = json.loads(
        (tmp_path / "state" / "missions" / "board.json").read_text(encoding="utf-8")
    )
    manifest = json.loads(
        (tmp_path / "state" / "takeover" / "manifest.json").read_text(encoding="utf-8")
    )
    assert board["missions"][0]["id"] == "m1"
    assert manifest["agents"]["items"] == [agent]


def test_load_state_remains_read_only_when_volume_state_is_missing(tmp_path):
    service = MissionLifecycleService(tmp_path)

    board, manifest = service.load_state()

    assert board["__invalid_state__"] is True
    assert manifest["__invalid_state__"] is True
    assert not (tmp_path / "state" / "missions" / "board.json").exists()
    assert not (tmp_path / "state" / "takeover" / "manifest.json").exists()
