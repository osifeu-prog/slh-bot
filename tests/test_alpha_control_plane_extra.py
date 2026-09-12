from core import alpha_control_plane


def test_alpha_report_matches_evaluation(monkeypatch):
    monkeypatch.setenv("RUN_BOT", "1")
    result = alpha_control_plane.evaluate()
    report = alpha_control_plane.format_report(result)
    assert result["status"] in {"READY", "BLOCKED"}
    assert f"BLOCKERS: {len(result['blockers'])}" in report
    assert f"STATUS: {result['status']}" in report
