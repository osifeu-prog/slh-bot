def test_alpha_control_plane_final_smoke():
    from core.alpha_control_plane import evaluate
    result = evaluate()
    assert result["status"] in {"READY", "BLOCKED"}
