import json
from pathlib import Path


def test_no_active_route_uses_legacy_lifecycle_execution():
    root = Path(__file__).resolve().parents[1]
    forbidden = ".execute_mission("
    checked = [
        root / "handlers" / "mission_handler.py",
        root / "core" / "mission_orchestrator.py",
        root / "core" / "mission_runtime_authority.py",
    ]
    offenders = [str(path.relative_to(root)) for path in checked if forbidden in path.read_text(encoding="utf-8")]
    assert offenders == []


def test_runtime_authority_requires_explicit_action_contract(monkeypatch, tmp_path):
    from core import mission_runtime_authority as authority

    board_dir = tmp_path / "state" / "missions"
    board_dir.mkdir(parents=True)
    (board_dir / "board.json").write_text(
        '{"missions":[{"id":"m1","desc":"legacy","status":"assigned","assigned_to":"agent-1"}]}',
        encoding="utf-8",
    )
    manifest_dir = tmp_path / "state" / "takeover"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "manifest.json").write_text(
        '{"agents":{"items":[{"id":"agent-1","name":"Agent 1","runtime_class":"MissionExecutorAgent","state":"idle"}]}}',
        encoding="utf-8",
    )

    called = {"runtime": False}

    class ExplodingRuntime:
        def execute(self, event):
            called["runtime"] = True
            raise AssertionError("runtime must not run without an action contract")

    result = authority.execute_mission_authority(
        mission_id="m1",
        root=tmp_path,
        runtime=ExplodingRuntime(),
    )

    assert result["status"] == "blocked"
    assert result["reason"] == "mission_execution_contract_missing"
    assert called["runtime"] is False


def test_runtime_authority_uses_canonical_runtime_service(monkeypatch, tmp_path):
    from core import mission_runtime_authority as authority

    board_dir = tmp_path / "state" / "missions"
    board_dir.mkdir(parents=True)
    (board_dir / "board.json").write_text(
        json.dumps({
            "missions": [{
                "id": "m2",
                "desc": "academy test",
                "status": "assigned",
                "assigned_to": "agent-2",
                "reward": 0,
                "action_type": "academy.complete_stage",
                "action_payload": {"course_id": "bitcoin_mastery", "stage": 1},
                "idempotency_key": "mission:m2:academy:bitcoin_mastery:1",
            }]
        }),
        encoding="utf-8",
    )
    manifest_dir = tmp_path / "state" / "takeover"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "manifest.json").write_text(
        json.dumps({
            "agents": {"items": [{
                "id": "agent-2",
                "name": "Agent 2",
                "runtime_class": "MissionExecutorAgent",
                "state": "idle",
            }]}
        }),
        encoding="utf-8",
    )

    seen = {}

    def canonical_execute(identifier, event):
        seen["identifier"] = identifier
        seen["event"] = event
        return {
            "type": "agent",
            "data": {
                "mission_id": "m2",
                "action_type": "academy.complete_stage",
                "idempotency_key": "mission:m2:academy:bitcoin_mastery:1",
                "execution_status": "success",
                "verified": True,
                "evidence": {"changed": True},
            },
        }

    monkeypatch.setattr(authority.runtime_service, "execute_agent_event", canonical_execute)

    result = authority.execute_mission_authority("m2", root=tmp_path)

    assert result["status"] == "completed"
    assert seen["identifier"] == "agent-2"
    assert seen["event"]["mission_id"] == "m2"
    assert seen["event"]["source"] == "mission_runtime_authority"
