from core import alpha_control_plane


def test_open_alpha_rejects_blocked_gate(monkeypatch):
    monkeypatch.setattr(alpha_control_plane, "evaluate", lambda: {
        "status": "BLOCKED", "blockers": [{"name": "x"}], "checks": [], "timestamp": 0
    })
    try:
        alpha_control_plane.open_alpha("owner")
    except RuntimeError as exc:
        assert "BLOCKED" in str(exc)
    else:
        assert False, "blocked Alpha must not open"
