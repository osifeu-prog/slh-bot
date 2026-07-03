class BaseModule:
    def handle(self, event):
        return {"ok": True, "event": event}


class TelegramModule(BaseModule):
    def handle(self, event):
        cmd = event.get("cmd", "")
        payload = event.get("payload", {})

        return {
            "module": "telegram",
            "cmd": cmd,
            "result": f"handled telegram event: {payload}"
        }
