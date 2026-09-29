"""Safe lifecycle controls for autonomous agents.

This module deliberately separates lifecycle from the existing runtime state.
Lifecycle transitions never delete agent data. Hard deletion remains an explicit,
out-of-band operation and is not represented by this state machine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

ENABLED: Final = "enabled"
DISABLED: Final = "disabled"
PAUSED: Final = "paused"
QUARANTINED: Final = "quarantined"

VALID_STATES: Final = frozenset({ENABLED, DISABLED, PAUSED, QUARANTINED})

ALLOWED_TRANSITIONS: Final = {
    ENABLED: frozenset({DISABLED, PAUSED, QUARANTINED}),
    DISABLED: frozenset({ENABLED, PAUSED, QUARANTINED}),
    PAUSED: frozenset({ENABLED, DISABLED, QUARANTINED}),
    QUARANTINED: frozenset({ENABLED, DISABLED, PAUSED}),
}

class InvalidLifecycleTransition(ValueError):
    """Raised when an agent lifecycle transition is not explicitly allowed."""

@dataclass(frozen=True)
class LifecycleDecision:
    old_state: str
    new_state: str
    changed: bool

def validate_state(state: str) -> str:
    state = str(state).strip().lower()
    if state not in VALID_STATES:
        raise ValueError(f"Invalid lifecycle state: {state}")
    return state

def transition(old_state: str, new_state: str) -> LifecycleDecision:
    old_state = validate_state(old_state)
    new_state = validate_state(new_state)
    if new_state not in ALLOWED_TRANSITIONS[old_state] and new_state != old_state:
        raise InvalidLifecycleTransition(
            f"Lifecycle transition not allowed: {old_state} -> {new_state}"
        )
    return LifecycleDecision(old_state, new_state, old_state != new_state)

def can_operate(state: str) -> bool:
    return validate_state(state) == ENABLED
