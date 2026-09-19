import time

from SLH_KERNEL import SLHKernel
from core.project_context import get_project_context
from core.action_router import dispatch as dispatch_action

KERNEL = SLHKernel()


class SLHGateway:
    def __init__(self):
        self.kernel = KERNEL
        print("🌐 Gateway ready (canonical project-aware mode)")

    def send(self, source, cmd, payload=None):
        payload = payload or {}
        event = {
            "source": source,
            "cmd": cmd,
            "payload": payload,
            "timestamp": time.time(),
        }

        # Canonical read-only gateway status comes from the Project Context.
        # Legacy module routing remains available for compatibility.
        if cmd == "status":
            return get_project_context(payload.get("user_id"))

        if isinstance(cmd, str) and cmd.startswith("action:"):
            action_name = cmd.split(":", 1)[1]
            return dispatch_action(action_name, payload.get("user_id"), **payload)

        return self.kernel.route(event)
