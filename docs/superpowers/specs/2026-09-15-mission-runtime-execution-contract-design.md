# Mission Runtime Execution Contract — Design Spec

**Date:** 2026-09-15  
**Status:** Draft for review  
**Scope:** Mission execution path only; no production deployment, Railway changes, economy migration, or ESP control.

## Goal

Replace the remaining synthetic Mission Executor path with a real, bounded Runtime invocation that can only execute an explicitly allow-listed mission capability and can only advance the Mission Lifecycle when the Runtime returns verifiable evidence.

## Current Problem

`core/mission_orchestrator.py` currently instantiates `MissionExecutorAgent` directly during the `execute` stage. The agent is correctly prevented from claiming success without an `execution_result`, but the orchestrator does not yet obtain a real execution result from the Kernel/Runtime. This leaves the lifecycle contract safe but incomplete: a mission can only proceed if a trusted caller supplies execution evidence, while the normal orchestrator path has no bounded runtime adapter that produces that evidence.

The existing `core/kernel.py` already exposes `call_agent(name, cmd, event)`, and `core/agent_factory.py` already uses an explicit runtime-class allow-list. The next step is to connect those existing boundaries rather than introduce a generic command executor.

## Proposed Architecture

```text
Mission
  -> MissionOrchestrator
  -> bounded Runtime Adapter
  -> SLHKernel.call_agent()
  -> registered MissionExecutorAgent
  -> allow-listed capability/action
  -> structured execution result + evidence
  -> MissionLifecycleService.execute_mission(...)
  -> executed
  -> completion lifecycle
```

### 1. Structured execution contract

The mission execution request is a structured event, not a shell command. It must contain:

- `mission_id`
- `capability`
- `action`
- `source`

The mission description is informational context only. It must never be interpreted as executable code or a shell command.

The first supported capability is `mission_execution` with action `execute_mission`.

### 2. Kernel boundary

The orchestrator must invoke the existing Kernel boundary rather than constructing `MissionExecutorAgent` itself. The Kernel remains responsible for resolving a registered runtime agent by name and returning its structured result.

The implementation must not add dynamic imports, arbitrary Python execution, shell execution, subprocess execution, network fetching, or filesystem commands to the Mission Executor.

### 3. Mission Executor boundary

`MissionExecutorAgent` becomes a bounded capability adapter. It may only accept the exact supported capability/action pair. Any other capability or action returns `blocked` with a stable reason.

A successful execution result must contain:

```python
{
    "execution_status": "success",
    "mission_id": "<id>",
    "capability": "mission_execution",
    "action": "execute_mission",
    "verified": True,
    "evidence": {...},
}
```

The evidence must be structured and attributable to the bounded runtime operation. The executor must not manufacture evidence that claims an external side effect occurred when no such operation was performed.

For the current stage, the bounded operation is the mission-runtime contract itself. It verifies that the request is structurally valid and that the registered runtime capability is available. It does not pretend to perform arbitrary mission work.

### 4. Lifecycle authority

`MissionLifecycleService.execute_mission()` remains the only component allowed to transition a mission from `assigned` to `executed`.

It must reject:

- missing execution result
- non-success execution status
- `verified` not exactly `True`
- missing evidence
- mismatched mission identity
- unsupported capability/action

No synthetic `synchronization_check`, `execution_check`, or equivalent placeholder may be inserted to make the lifecycle pass.

### 5. Failure semantics

Every rejected execution is terminal for that invocation and returns `blocked` without changing mission state.

Examples:

- runtime unavailable -> `blocked`
- unknown runtime agent -> `blocked`
- unsupported capability/action -> `blocked`
- invalid evidence -> `blocked`
- lifecycle validation failure -> `blocked`

The orchestrator must preserve the failure reason and runtime evidence in its returned result without mutating mission state on failure.

### 6. Idempotency / retry boundary

A repeated execution request for an already executed mission must not create a second lifecycle transition. The existing lifecycle state machine remains authoritative. Runtime invocation must be deterministic for the same structured request and must not create financial side effects.

Mission rewards and economy writes are explicitly outside this change.

## Security Constraints

1. No generic shell executor.
2. No `subprocess`, `os.system`, shell parsing, or arbitrary Python evaluation.
3. No dynamic runtime-class import from mission data.
4. No network I/O from MissionExecutorAgent.
5. No ESP commands or device control.
6. No Railway API calls.
7. No direct state/DB mutation by the Runtime Agent.
8. No mission description to command conversion.
9. Runtime capability must be allow-listed.
10. Lifecycle state changes remain behind `MissionLifecycleService`.

## Files Expected to Change

### Modify

- `core/mission_orchestrator.py` — replace direct `MissionExecutorAgent().process(...)` construction with the Kernel/runtime boundary and normalize runtime failures.
- `agents/mission_executor.py` — enforce exact capability/action contract and return only structured bounded execution evidence.
- `core/kernel.py` — only if a minimal typed/validated helper is required; preserve existing `call_agent()` compatibility.
- `core/agent_factory.py` — only if the runtime manifest needs a precise capability declaration; do not broaden the allow-list.

### Tests

- `tests/test_mission_execution_contract.py` — extend contract coverage for Kernel invocation, capability allow-list, evidence validation, and blocked failure paths.
- Add a focused orchestrator test if the existing suite does not already isolate `run_next_action()`.

### CI

- Keep `.github/workflows/mission-execution-boundary.yml` as the dedicated boundary gate.
- The workflow must remain independent of Railway and production state.

## Verification Criteria

The implementation is acceptable only when all of the following are proven:

1. The orchestrator reaches the Mission Executor through `SLHKernel.call_agent()`.
2. Direct construction of `MissionExecutorAgent` is absent from the orchestrator execution path.
3. Unsupported capability/action is blocked.
4. Missing or invalid evidence is blocked.
5. A valid bounded runtime result advances the lifecycle to `executed`.
6. A blocked runtime result leaves the mission state unchanged.
7. Repeated execution does not duplicate the lifecycle transition.
8. Mission description is never executed as code or a shell command.
9. No production files/state are modified by the tests.
10. The dedicated mission execution boundary CI is green.

## Explicit Non-Goals

This spec does not implement:

- arbitrary autonomous shell execution
- remote code execution
- ESP firmware execution/control
- production deployment
- Railway configuration changes
- payment/economy changes
- mission reward issuance
- a new worker/poller
- a general-purpose agent orchestration framework

Those are separate architectural decisions.
