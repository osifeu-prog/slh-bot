from core import alpha_control_plane


def test_open_alpha_is_gate_protected(monkeypatch):
    monkeypatch.setattr(alpha_control_plane, "evaluate", lambda: {
        "status": "BLOCKED",
        "blockers": [{"name": "test", "status": "FAIL"}],
        "checks": [],
        "timestamp": 0,
    })
    try:
        alpha_control_plane.open_alpha("owner")
    except RuntimeError as exc:
        assert "STATUS: BLOCKED" in str(exc)
    else:
        raise AssertionError("blocked Alpha must not open")
