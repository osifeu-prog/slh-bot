from core import alpha_control_plane


def test_alpha_control_plane_evaluator_has_stable_shape(monkeypatch):
    monkeypatch.setenv("RUN_BOT", "1")
    result = alpha_control_plane.evaluate()
    assert result["status"] in {"READY", "BLOCKED"}
    assert isinstance(result["checks"], list)
    assert isinstance(result["blockers"], list)
    assert len(result["checks"]) >= 1
    assert all(c["status"] in {"PASS", "FAIL"} for c in result["checks"])


def test_format_report_is_deterministic_shape(monkeypatch):
    monkeypatch.setenv("RUN_BOT", "1")
    result = alpha_control_plane.evaluate()
    report = alpha_control_plane.format_report(result)
    assert report.startswith("ALPHA CONTROL PLANE")
    assert f"BLOCKERS: {len(result['blockers'])}" in report
    assert f"STATUS: {result['status']}" in report


def test_open_alpha_rejects_non_owner_without_state_write(monkeypatch):
    monkeypatch.setattr(alpha_control_plane, "is_owner", lambda _uid: False)
    monkeypatch.setattr(
        alpha_control_plane.state_manager,
        "atomic_update",
        lambda _mutate: (_ for _ in ()).throw(AssertionError("state write attempted")),
    )
    try:
        alpha_control_plane.open_alpha("not-owner")
    except PermissionError as exc:
        assert str(exc) == "Owner only."
    else:
        raise AssertionError("non-owner unexpectedly opened Alpha")
