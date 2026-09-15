# Mission Runtime Execution Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the remaining direct MissionExecutorAgent invocation with a real, bounded Kernel/runtime path that can advance a mission only from validated structured execution evidence.

**Architecture:** MissionOrchestrator will invoke the existing SLHKernel.call_agent() boundary using a structured capability/action event. MissionExecutorAgent will accept only the allow-listed `mission_execution / execute_mission` contract and return deterministic, structured evidence for the bounded runtime-contract operation; MissionLifecycleService remains the sole state-transition authority.

**Tech Stack:** Python 3.11, pytest, existing SLHKernel, MissionOrchestrator, MissionLifecycleService, MissionExecutorAgent, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-15-mission-runtime-execution-contract-design.md`

## Global Constraints

- No generic shell executor, subprocess, os.system, shell parsing, or arbitrary Python evaluation.
- No dynamic runtime-class import from mission data.
- No network I/O from MissionExecutorAgent.
- No ESP commands/device control.
- No Railway API calls or production deployment.
- No direct state/DB mutation by MissionExecutorAgent.
- Mission descriptions are informational context only and are never converted to commands.
- Runtime capability/action is explicitly allow-listed.
- MissionLifecycleService remains the only authority for `assigned -> executed`.
- Mission rewards and economy writes are outside this change.
- Dedicated CI must remain independent of Railway and production state.

---

### Task 1: Lock the runtime contract with focused failing tests

**Files:**
- Modify: `tests/test_mission_execution_contract.py`
- Test/inspect: `core/mission_orchestrator.py`, `core/kernel.py`, `agents/mission_executor.py`

**Interfaces:**
- Consumes: existing `MissionOrchestrator.run_next_action()`, `SLHKernel.call_agent()`, and MissionExecutorAgent contract.
- Produces: tests proving the orchestrator uses Kernel, unsupported capability/action is blocked, valid evidence executes, blocked execution preserves state, and repeated execution is idempotent.

- [ ] **Step 1: Fetch the current branch versions of the contract test and implementation files and identify the existing test fixtures/helpers.**

- [ ] **Step 2: Add a failing test that replaces/guards against direct `MissionExecutorAgent().process()` construction in the orchestrator path by injecting a Kernel and asserting `call_agent()` receives the structured event.**

```python
def test_orchestrator_invokes_kernel_runtime_boundary(monkeypatch, mission_runtime_fixture):
    calls = []

    class FakeKernel:
        def call_agent(self, name, cmd, event):
            calls.append((name, cmd, event))
            return {
                "type": "agent",
                "data": {
                    "execution_status": "success",
                    "mission_id": event["mission_id"],
                    "capability": "mission_execution",
                    "action": "execute_mission",
                    "verified": True,
                    "evidence": {"kind": "runtime_contract", "validated": True},
                },
            }

    orchestrator = mission_runtime_fixture.kernel_orchestrator(FakeKernel())
    result = orchestrator.run_next_action(mission_id=mission_runtime_fixture.mission_id)

    assert calls
    assert calls[0][0] == "MissionExecutorAgent"
    assert calls[0][1] == "Mission Executor:execute_mission"
    assert calls[0][2]["capability"] == "mission_execution"
    assert calls[0][2]["action"] == "execute_mission"
    assert result["status"] == "executed"
```

- [ ] **Step 3: Add a failing executor test for unsupported capability/action.**

```python
def test_executor_blocks_unsupported_capability():
    result = MissionExecutorAgent().process({
        "cmd": "Mission Executor:execute_mission",
        "mission_id": "m-1",
        "capability": "shell",
        "action": "run",
        "source": "test",
    })
    assert result["execution_status"] == "blocked"
    assert result["reason"] == "unsupported_capability_action"
```

- [ ] **Step 4: Add a failing lifecycle/orchestrator test that a valid structured evidence result advances the mission to `executed`, while a blocked runtime result leaves the mission assigned.**

- [ ] **Step 5: Add a failing test that an already executed mission cannot create a second lifecycle transition.**

- [ ] **Step 6: Run only the focused contract suite and confirm the new tests fail for the intended pre-implementation reasons.**

Run: `pytest tests/test_mission_execution_contract.py -q`
Expected: FAIL in the newly added Kernel/capability/idempotency assertions; existing passing tests remain passing.

---

### Task 2: Make MissionExecutorAgent a strict bounded capability adapter

**Files:**
- Modify: `agents/mission_executor.py`
- Test: `tests/test_mission_execution_contract.py`

**Interfaces:**
- Consumes: structured event with `mission_id`, `capability`, `action`, and `source`.
- Produces: deterministic result with `execution_status`, mission identity, capability/action, `verified`, and structured evidence, or `blocked` with a stable reason.

- [ ] **Step 1: Write/confirm the failing tests for missing mission identity, missing capability/action, unsupported capability/action, and malformed event input.**

- [ ] **Step 2: Implement the minimal exact allow-list: `mission_execution` + `execute_mission`; reject everything else without side effects.**

```python
SUPPORTED_CAPABILITY = "mission_execution"
SUPPORTED_ACTION = "execute_mission"

if event.get("capability") != SUPPORTED_CAPABILITY or event.get("action") != SUPPORTED_ACTION:
    return {
        "execution_status": "blocked",
        "mission_id": str(event.get("mission_id", "")),
        "reason": "unsupported_capability_action",
    }
```

- [ ] **Step 3: Implement deterministic bounded evidence describing only validation of the registered runtime capability, not an external side effect.**

```python
return {
    "execution_status": "success",
    "mission_id": str(event["mission_id"]),
    "capability": SUPPORTED_CAPABILITY,
    "action": SUPPORTED_ACTION,
    "verified": True,
    "evidence": {
        "kind": "runtime_contract",
        "validated": True,
        "external_side_effect": False,
    },
}
```

- [ ] **Step 4: Explicitly keep the executor free of subprocess, os.system, network calls, dynamic imports, and state/DB writes.**

- [ ] **Step 5: Run the focused executor tests and verify they pass.**

Run: `pytest tests/test_mission_execution_contract.py -q`
Expected: PASS for executor contract tests; orchestrator integration tests may still fail until Task 3.

- [ ] **Step 6: Commit the bounded executor change.**

```bash
git add agents/mission_executor.py tests/test_mission_execution_contract.py
git commit -m "feat: enforce bounded mission runtime capability"
```

---

### Task 3: Route MissionOrchestrator through the Kernel

**Files:**
- Modify: `core/mission_orchestrator.py`
- Test: `tests/test_mission_execution_contract.py`

**Interfaces:**
- Consumes: `SLHKernel.call_agent(name, cmd, event)` and Task 2 executor contract.
- Produces: orchestrator execution path that never directly constructs MissionExecutorAgent and passes only structured runtime events to Kernel.

- [ ] **Step 1: Add a focused test seam allowing `MissionOrchestrator` to receive a Kernel instance without changing existing callers that instantiate it with only `root`.**

- [ ] **Step 2: Replace direct `MissionExecutorAgent().process(...)` construction in the execute branch with `kernel.call_agent(...)`.**

```python
runtime_response = self.kernel.call_agent(
    "MissionExecutorAgent",
    "Mission Executor:execute_mission",
    {
        "mission_id": str(mission_id),
        "capability": "mission_execution",
        "action": "execute_mission",
        "source": "mission_orchestrator",
    },
)
```

- [ ] **Step 3: Normalize Kernel errors and agent `blocked` results to the orchestrator's existing blocked result shape without changing mission state.**

- [ ] **Step 4: Pass only `runtime_response["data"]` as `execution_result` to `MissionLifecycleService.execute_mission()`.**

- [ ] **Step 5: Run the focused contract suite and verify the Kernel invocation and valid execution path pass.**

Run: `pytest tests/test_mission_execution_contract.py -q`
Expected: PASS with zero failures.

- [ ] **Step 6: Commit the orchestrator/runtime-boundary change.**

```bash
git add core/mission_orchestrator.py tests/test_mission_execution_contract.py
git commit -m "feat: route mission execution through kernel runtime"
```

---

### Task 4: Verify lifecycle identity, evidence, failure, and retry semantics

**Files:**
- Modify: `core/mission_lifecycle.py` only if a focused contract assertion exposes a missing validation already required by the Spec.
- Test: `tests/test_mission_execution_contract.py`

**Interfaces:**
- Consumes: structured runtime execution result from Task 3.
- Produces: lifecycle transition only when mission identity, exact success state, verification, evidence, and supported capability/action all match.

- [ ] **Step 1: Add tests for mismatched `mission_id`, `execution_status != success`, `verified is not True`, missing evidence, and unsupported capability/action.**

- [ ] **Step 2: Add a test that each rejected result leaves the mission status exactly `assigned`.**

- [ ] **Step 3: Add a retry test that executing an already executed mission returns the existing lifecycle state without a second transition or additional execution-side mutation.**

- [ ] **Step 4: Run the complete focused suite.**

Run: `pytest tests/test_mission_execution_contract.py -q`
Expected: PASS, zero failures.

- [ ] **Step 5: If lifecycle code requires a change, make the smallest validation-only change and rerun the focused suite. If no change is required, leave `core/mission_lifecycle.py` untouched.**

- [ ] **Step 6: Commit only lifecycle changes if they were necessary.**

```bash
git add core/mission_lifecycle.py tests/test_mission_execution_contract.py
git commit -m "test: verify mission execution lifecycle boundaries"
```

---

### Task 5: Verify runtime registry/manifest remains bounded

**Files:**
- Inspect: `core/agent_factory.py`
- Test: `tests/test_mission_execution_contract.py`
- Modify: `core/agent_factory.py` only if the existing manifest does not accurately declare the bounded MissionExecutor capability.

**Interfaces:**
- Consumes: existing explicit `AGENT_CLASS_MAP` and `RUNTIME_MANIFESTS`.
- Produces: explicit `MissionExecutorAgent` manifest declaring `mission_execution`, with no expansion to arbitrary runtime classes.

- [ ] **Step 1: Add a test asserting `MissionExecutorAgent` is registered explicitly and its manifest contains only the `mission_execution` capability.**

- [ ] **Step 2: Run the test and inspect the existing manifest.**

Run: `pytest tests/test_mission_execution_contract.py -q`
Expected: PASS without broadening the registry.

- [ ] **Step 3: If and only if the manifest assertion fails, update the manifest to match the Spec and rerun the focused suite.**

- [ ] **Step 4: Compile the touched Python modules.**

Run: `python -m compileall -q agents/mission_executor.py core/mission_orchestrator.py core/mission_lifecycle.py core/kernel.py core/agent_factory.py tests/test_mission_execution_contract.py`
Expected: exit code 0.

---

### Task 6: Run dedicated CI and final local verification

**Files:**
- Inspect/modify only if required: `.github/workflows/mission-execution-boundary.yml`

**Interfaces:**
- Consumes: all implementation changes from Tasks 1–5.
- Produces: a CI gate proving the mission execution boundary independently of Railway and production state.

- [ ] **Step 1: Run the focused contract suite one final time.**

Run: `pytest tests/test_mission_execution_contract.py -q`
Expected: PASS with zero failures.

- [ ] **Step 2: Run syntax compilation for every touched Python module.**

Run: `python -m compileall -q agents/mission_executor.py core/mission_orchestrator.py core/mission_lifecycle.py core/kernel.py core/agent_factory.py tests/test_mission_execution_contract.py`
Expected: exit code 0.

- [ ] **Step 3: Inspect the final diff and confirm there is no `subprocess`, `os.system`, shell execution, dynamic import, network I/O, Railway API call, ESP command, or direct DB/state mutation added to the Mission Executor path.**

- [ ] **Step 4: Confirm `.github/workflows/mission-execution-boundary.yml` runs only the dedicated contract tests and does not access production state.**

- [ ] **Step 5: Verify PR #72 remains Draft and no Railway deployment has been triggered.**

- [ ] **Step 6: Push/commit all verified changes on `feat/mission-real-execution-contract`; do not merge PR #72 and do not deploy production.**

- [ ] **Step 7: Read the final CI result and record the exact run/job status before claiming the boundary is green.**

---

## Self-Review Checklist

- Spec coverage: structured event, Kernel boundary, bounded executor, lifecycle authority, failure semantics, retry/idempotency, security constraints, non-goals, and dedicated CI are each covered by Tasks 1–6.
- No generic executor is introduced.
- No mission description is interpreted as executable input.
- No production/economy/ESP/Railway changes are included.
- Interfaces use the existing Kernel and Lifecycle APIs wherever possible.
- Every task has a concrete test/verification command.
- No task relies on a placeholder or unspecified implementation.
