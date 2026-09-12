def test_alpha_control_plane_imports():
    from core.alpha_control_plane import evaluate, format_report
    result = evaluate()
    assert result["status"] in ("READY", "BLOCKED")
    assert format_report(result).startswith("ALPHA CONTROL PLANE")
