"""Deterministic, read-only autonomy coordinator.

This module does not mutate state, deploy services, change authority, or settle
funds. It combines existing canonical readiness/runtime signals into one
machine-readable next-action decision for the future autonomous control loop.
"""

from __future__ import annotations

from core.alpha_control_plane import evaluate as evaluate_alpha
from core.runtime_service import status as runtime_status


SAFE_AUTOMATION = "SAFE_AUTOMATION"
HUMAN_GATE = "HUMAN_GATE"
BLOCKED = "BLOCKED"


def observe() -> dict:
    """Collect existing canonical signals without performing a mutation."""
    alpha = evaluate_alpha()
    runtime = runtime_status()

    running = bool(runtime.get("running"))
    runtime_state = runtime.get("state")
    agent_count = len(runtime.get("agents", []) or [])

    return {
        "alpha": alpha,
        "runtime": {
            "state": runtime_state,
            "running": running,
            "boot_ok": runtime.get("boot_ok"),
            "agent_count": agent_count,
            "queue_size": runtime.get("queue_size"),
            "thread_alive": runtime.get("thread_alive"),
        },
    }


def decide(observation: dict) -> dict:
    """Return the next deterministic action class; never execute it."""
    alpha = observation.get("alpha") or {}
    runtime = observation.get("runtime") or {}

    if alpha.get("status") != "READY":
        return {
            "class": BLOCKED,
            "action": "diagnose_alpha_blockers",
            "reason": "alpha readiness is not READY",
        }

    if alpha.get("system_status") != "READY":
        return {
            "class": BLOCKED,
            "action": "diagnose_system_blockers",
            "reason": "system readiness is degraded",
        }

    if not runtime.get("running"):
        return {
            "class": BLOCKED,
            "action": "runtime_recovery",
            "reason": "canonical runtime is not running",
        }

    if not runtime.get("thread_alive"):
        return {
            "class": BLOCKED,
            "action": "runtime_thread_recovery",
            "reason": "runtime reports running but worker thread is not alive",
        }

    return {
        "class": SAFE_AUTOMATION,
        "action": "continue_control_loop",
        "reason": "alpha, system, and runtime gates are ready",
    }


def plan() -> dict:
    """Produce an auditable observation + decision plan.

    This is intentionally planning-only. Execution belongs behind the existing
    canonical authority and explicit financial/on-chain gates.
    """
    observation = observe()
    decision = decide(observation)
    return {
        "status": "READY" if decision["class"] == SAFE_AUTOMATION else decision["class"],
        "observation": observation,
        "decision": decision,
        "financial_settlement": {
            "class": HUMAN_GATE,
            "action": "require_explicit_production_gate",
        },
    }
