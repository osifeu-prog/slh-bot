from core import alpha_control_plane


def test_alpha_state_defaults_to_empty_dict(monkeypatch):
    monkeypatch.setattr(alpha_control_plane.state_manager, "load_db", lambda: {})
    assert alpha_control_plane.alpha_state() == {}
