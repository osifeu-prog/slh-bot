"""Safe autonomous supervisor for the canonical control plane.

The supervisor is intentionally read-only. It continuously observes the existing
autonomy control plane and records the deterministic decision. It does not mutate
state, deploy code, change authority, or settle funds.
"""

from __future__ import annotations

import os
import threading
import time

from core.autonomy_control_plane import plan

_DEFAULT_INTERVAL = 120
_STOP = threading.Event()
_THREAD = None
_LOCK = threading.Lock()


def _interval() -> int:
    try:
        return max(30, int(os.getenv("SLH_AUTONOMY_INTERVAL_SECONDS", _DEFAULT_INTERVAL)))
    except (TypeError, ValueError):
        return _DEFAULT_INTERVAL


def run_once(logger=print) -> dict:
    """Observe the canonical control plane once and emit an auditable decision."""
    result = plan()
    decision = result.get("decision") or {}
    logger(
        "[AUTONOMY] "
        f"status={result.get('status')} "
        f"class={decision.get('class')} "
        f"action={decision.get('action')} "
        f"reason={decision.get('reason')}"
    )
    return result


def _run_forever(logger=print) -> None:
    interval = _interval()
    logger(f"[AUTONOMY] Supervisor started; interval={interval}s; mode=READ_ONLY")
    while not _STOP.is_set():
        try:
            run_once(logger=logger)
        except Exception as exc:
            logger(f"[AUTONOMY] Supervisor cycle failed: {type(exc).__name__}")
        _STOP.wait(interval)
    logger("[AUTONOMY] Supervisor stopped")


def start(logger=print) -> bool:
    """Start one daemon supervisor thread; safe to call repeatedly."""
    global _THREAD
    with _LOCK:
        if _THREAD is not None and _THREAD.is_alive():
            return False
        _STOP.clear()
        _THREAD = threading.Thread(
            target=_run_forever,
            args=(logger,),
            daemon=True,
            name="slh-autonomy-supervisor",
        )
        _THREAD.start()
        return True


def stop() -> None:
    """Stop the supervisor on controlled process shutdown/tests."""
    _STOP.set()


def status() -> dict:
    """Return supervisor state without changing it."""
    thread = _THREAD
    return {
        "running": bool(thread and thread.is_alive()),
        "interval_seconds": _interval(),
        "mode": "READ_ONLY",
    }
