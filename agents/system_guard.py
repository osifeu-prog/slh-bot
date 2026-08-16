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

        return {
            "agent": "SystemGuard",
            "status": "ok",
            "checks": {
                "runtime": "available",
                "kernel": "available",
                "event": "received",
            },
            "event": {
                "cmd": event.get("cmd"),
                "source": event.get("source"),
            },
        }
