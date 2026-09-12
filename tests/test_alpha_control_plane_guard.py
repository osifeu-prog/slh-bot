def test_alpha_status_values():
    from core.alpha_control_plane import evaluate
    assert evaluate()["status"] in ("READY", "BLOCKED")
