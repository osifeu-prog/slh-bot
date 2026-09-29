# Safe Agent Lifecycle

The agent lifecycle is separate from the existing runtime state (idle, active, error).

## Lifecycle states
- enabled: execution is permitted.
- disabled: execution is blocked; state and history remain intact.
- paused: execution is temporarily blocked; state and history remain intact.
- quarantined: execution is blocked pending explicit review.

## Safety contract
1. Lifecycle operations never delete agent records.
2. Every transition is explicit and validated.
3. Lifecycle changes should be auditable.
4. Runtime state remains independent from lifecycle state.
5. Hard deletion is intentionally outside this state machine.

## Rollout
This branch is a dormant, reviewable control-plane change. Production behavior should
not change until the lifecycle gate is integrated and verified against the existing
agent registry and runtime dispatch paths.
