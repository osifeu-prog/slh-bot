def test_alpha_status_field():
    from core.alpha_control_plane import evaluate
    assert evaluate().get("status") in ("READY", "BLOCKED")
