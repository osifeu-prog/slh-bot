"""
SLH SystemGuardAgent
Stage 22A

Read-only runtime agent.

Responsibilities:
- Receive runtime events
- Validate basic event structure
- Report runtime-level health
- Never mutate DB
- Never execute shell commands
- Never control Telegram
- Never activate other agents
"""

class SystemGuardAgent:

    def __init__(self, context=None):
        self.context = context or {}

    def process(self, event):

        if not isinstance(event, dict):
            return {
                "agent": "SystemGuard",
                "status": "error",
                "error": "event must be a dictionary",
            }

        cmd = str(event.get("cmd") or "")

        if cmd.endswith(":execute_mission"):
            return {
                "agent": "SystemGuard",
                "status": "ok",
                "execution_status": "failed",
                "mission_id": str(event.get("mission_id")),
                "reason": "systemguard_is_read_only_observer",
                "checks": {
                    "runtime": "available",
                    "kernel": "available",
                    "event": "received",
                    "mission_executor": "unavailable",
                },
                "event": {
                    "cmd": cmd,
                    "source": event.get("source"),
                },
            }

        return {
            "agent": "SystemGuard",
            "status": "ok",
            "checks": {
                "runtime": "available",
                "kernel": "available",
                "event": "received",
            },
            "event": {
                "cmd": cmd,
                "source": event.get("source"),
            },
        }
