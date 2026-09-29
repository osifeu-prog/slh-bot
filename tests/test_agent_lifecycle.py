from core.agent_lifecycle import (
    DISABLED, ENABLED, PAUSED, QUARANTINED,
    transition, can_operate,
)

def test_disable_preserves_data_semantics():
    decision = transition(ENABLED, DISABLED)
    assert decision.changed is True
    assert can_operate(DISABLED) is False

def test_pause_and_resume():
    assert transition(ENABLED, PAUSED).new_state == PAUSED
    assert transition(PAUSED, ENABLED).new_state == ENABLED

def test_quarantine_is_explicit():
    assert transition(ENABLED, QUARANTINED).new_state == QUARANTINED
    assert can_operate(QUARANTINED) is False

def test_invalid_state_is_rejected():
    assert transition(ENABLED, ENABLED).changed is False
    try:
        transition("unknown", ENABLED)
    except ValueError:
        pass
    else:
        raise AssertionError("unknown lifecycle state must fail")

def test_lifecycle_does_not_model_delete():
    assert "deleted" not in {ENABLED, DISABLED, PAUSED, QUARANTINED}
