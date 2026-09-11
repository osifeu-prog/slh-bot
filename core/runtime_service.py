import threading

from core.agent_factory import (
    create_validated_agent_from_record,
    load_agents_into_kernel,
)
from core.agent_registry import get_agent
from core.kernel import SLHKernel
from core.runtime import Runtime

_LOCK = threading.RLock()
_KERNEL = None
_RUNTIME = None
_BOOT_REPORT = None


def boot():
    """Start the canonical agent runtime once and load DB agents safely."""
    global _KERNEL, _RUNTIME, _BOOT_REPORT
    with _LOCK:
        if _RUNTIME is not None and _RUNTIME.status().get("running"):
            return _BOOT_REPORT

        _KERNEL = SLHKernel()
        _BOOT_REPORT = load_agents_into_kernel(_KERNEL)
        _RUNTIME = Runtime(_KERNEL)
        _RUNTIME.start()
        return _BOOT_REPORT


def _ensure_loaded(identifier):
    """Load a newly-created DB agent into the running kernel."""
    boot()
    agent_id, record = get_agent(identifier)
    if record is None:
        raise KeyError(f"Agent '{identifier}' not found")

    name = str(record.get("name") or agent_id)
    with _LOCK:
        if name not in _KERNEL.agents:
            runtime_agent = create_validated_agent_from_record(record)
            _KERNEL.register(name, runtime_agent)
    return agent_id, record, name


def execute_agent(identifier, command, source=None):
    """Execute a validated DB agent through the canonical Runtime/Dispatcher."""
    global _RUNTIME
    _, record, name = _ensure_loaded(identifier)
    if not record.get("runtime_class"):
        raise ValueError("Agent record has no runtime_class")

    event = {
        "cmd": f"{name}:{str(command)}",
        "source": source,
    }
    with _LOCK:
        return _RUNTIME.execute(event)


def status():
    boot()
    with _LOCK:
        return _RUNTIME.snapshot()


def boot_report():
    boot()
    with _LOCK:
        return _BOOT_REPORT
