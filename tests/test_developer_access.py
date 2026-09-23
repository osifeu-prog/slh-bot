import json
import importlib
from pathlib import Path


def seed_db(path, uid="100"):
    path.write_text(
        json.dumps(
            {
                "users": {
                    uid: {
                        "role": "student",
                        "academy": {
                            "courses": {
                                "bitcoin_mastery": {
                                    "stage": 0,
                                    "completed": [],
                                }
                            }
                        },
                    }
                }
            }
        ),
        encoding="utf-8",
    )


def load_module(monkeypatch, tmp_path, monkeypatcher):
    import state_manager
    monkeypatch.setattr(state_manager, "DB_FILE", str(tmp_path / "db.json"))
    monkeypatch.setattr(state_manager, "_LOCK_PATH", str(tmp_path / "db.json.lock"))

    from core import developer_access
    return importlib.reload(developer_access)


def test_bitcoin_mastery_is_required(tmp_path, monkeypatch):
    db = tmp_path / "db.json"
    seed_db(db)
    service = load_module(monkeypatch, tmp_path, None)

    result = service.prerequisite_status("100")
    assert result["ok"] is False
    assert result["reason"] == "bitcoin_mastery_incomplete"

    import state_manager
    data = state_manager.load_db()
    data["users"]["100"]["academy"]["courses"]["bitcoin_mastery"] = {
        "stage": 12,
        "completed": list(range(1, 13)),
    }
    state_manager.save_db(data)

    result = service.prerequisite_status("100")
    assert result["ok"] is True
    assert result["completed"] == 12
    assert result["required"] == 12


def test_request_is_idempotent(tmp_path, monkeypatch):
    db = tmp_path / "db.json"
    seed_db(db)
    service = load_module(monkeypatch, tmp_path, None)

    import state_manager
    data = state_manager.load_db()
    data["users"]["100"]["academy"]["courses"]["bitcoin_mastery"] = {
        "stage": 12,
        "completed": list(range(1, 13)),
    }
    state_manager.save_db(data)

    first = service.request_access("100")
    second = service.request_access("100")

    assert first["ok"] is True
    assert first["status"] == "pending"
    assert second["ok"] is True
    assert second["status"] == "pending"

    stored = state_manager.load_db()["developer_access_requests"]["100"]
    assert stored["status"] == "pending"


def test_approval_rechecks_course_and_sets_developer_role(tmp_path, monkeypatch):
    db = tmp_path / "db.json"
    seed_db(db)
    service = load_module(monkeypatch, tmp_path, None)

    import state_manager
    data = state_manager.load_db()
    data["users"]["100"]["academy"]["courses"]["bitcoin_mastery"] = {
        "stage": 12,
        "completed": list(range(1, 13)),
    }
    state_manager.save_db(data)

    assert service.request_access("100")["ok"] is True
    result = service.approve_access("100", "8789977826")

    assert result["ok"] is True
    assert result["status"] == "approved"

    data = state_manager.load_db()
    user = data["users"]["100"]
    assert user["role"] == "developer"
    assert user["developer_access_status"] == "active"
    assert "agents.view_all" in user["permissions"]
    assert data["developer_access_requests"]["100"]["status"] == "approved"


def test_non_owner_cannot_approve(tmp_path, monkeypatch):
    db = tmp_path / "db.json"
    seed_db(db)
    service = load_module(monkeypatch, tmp_path, None)
    import state_manager
    data = state_manager.load_db()
    data["users"]["100"]["academy"]["courses"]["bitcoin_mastery"] = {
        "stage": 12,
        "completed": list(range(1, 13)),
    }
    state_manager.save_db(data)

    service.request_access("100")
    result = service.approve_access("100", "200")
    assert result["ok"] is False
    assert result["reason"] == "owner_only"
