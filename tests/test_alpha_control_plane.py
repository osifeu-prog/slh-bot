from core import alpha_control_plane


def test_alpha_control_plane_evaluator_has_stable_shape(monkeypatch):
    monkeypatch.setenv("RUN_BOT", "1")
    result = alpha_control_plane.evaluate()
    assert result["status"] in {"READY", "BLOCKED"}
    assert isinstance(result["checks"], list)
    assert isinstance(result["blockers"], list)
    assert len(result["checks"]) >= 1
    assert all(c["status"] in {"PASS", "FAIL"} for c in result["checks"])
    assert all(c["scope"] in {"alpha", "system"} for c in result["checks"])
    assert result["status"] in {"READY", "BLOCKED"}
    assert result["system_status"] in {"READY", "DEGRADED"}


def test_format_report_is_deterministic_shape(monkeypatch):
    monkeypatch.setenv("RUN_BOT", "1")
    result = alpha_control_plane.evaluate()
    report = alpha_control_plane.format_report(result)
    assert report.startswith("ALPHA CONTROL PLANE")
    assert f"ALPHA BLOCKERS: {len(result['blockers'])}" in report
    assert f"ALPHA STATUS: {result['status']}" in report
    assert f"SYSTEM STATUS: {result['system_status']}" in report


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


def test_alpha_user_journey_contracts_are_explicit(monkeypatch):
    monkeypatch.setenv("RUN_BOT", "1")
    result = alpha_control_plane.evaluate()
    names = {check["name"] for check in result["checks"]}
    required = {
        "entry_onboarding",
        "join_chain",
        "personal_agent",
        "academy_authority",
        "academy_lesson_1",
        "referral_chain",
        "referral_authority",
        "stars_payment_handler",
        "stars_payment_authority",
        "stars_price_authority",
        "gate_safety",
        "staking_commands",
    }
    assert required <= names
    assert all(
        check["status"] == "PASS"
        for check in result["checks"]
        if check["name"] in required
    )


def test_alpha_gate_safety_is_read_only(monkeypatch):
    monkeypatch.setenv("RUN_BOT", "1")
    ok, detail = alpha_control_plane._evaluate_safety()
    assert ok is True
    assert "read-only" in detail


def test_join_handler_gates_completion_on_academy_initialization(monkeypatch):
    from pathlib import Path
    import ast

    source = Path("handlers/join_handler.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
    }
    assert "academy_started" in names
    assert "start_course" in names


def test_staking_contract_is_alpha_critical(monkeypatch):
    monkeypatch.setenv("RUN_BOT", "1")
    result = alpha_control_plane.evaluate()
    check = next(c for c in result["checks"] if c["name"] == "staking_commands")
    assert check["scope"] == "alpha"
    assert check["status"] == "PASS"
