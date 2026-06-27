

class TelegramAgent:

    def handle(self, event):
        cmd = event.get("cmd", "")

        if "ping" in cmd:
            return {
                "output": "pong",
                "score": 0.9,
                "value": 0.01
            }

        return {
            "output": f"telegram processed: {cmd}",
            "score": 0.6,
            "value": 0.0
        }


class AnalyticsAgent:

    def handle(self, event):
        return {
            "output": f"analytics logged: {event.get('cmd')}",
            "score": 0.4,
            "value": 0.0
        }


class RevenueAgent:

    def handle(self, event):
        value = event.get("value", 0)

        return {
            "output": f"revenue processed: {value}",
            "score": 0.3,
            "value": value
        }
