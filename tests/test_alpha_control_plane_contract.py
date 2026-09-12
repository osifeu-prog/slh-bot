def test_alpha_contract_output():
    from core.alpha_control_plane import evaluate
    result = evaluate()
    assert set(("status", "blockers", "checks", "timestamp")) <= set(result)
