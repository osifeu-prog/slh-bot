class TelegramAgent:
    def handle(self, event):
        cmd = event.get("cmd", "")

        if "ping" in cmd:
            return {"output": "pong", "score": 0.95, "value": 0.01}

        return {"output": f"telegram {cmd}", "score": 0.6, "value": 0.0}


class SmartAgent:
    def handle(self, event):
        cmd = event.get("cmd", "")
        score = 0.85 if "telegram" in cmd else 0.5
        return {"output": f"smart {cmd}", "score": score, "value": 0.0}


class AnalyticsAgent:
    def handle(self, event):
        return {"output": f"analytics {event.get('cmd')}", "score": 0.55, "value": 0.0}
