class LoggerPlugin:
    def handle(self, event):
        return {
            "output": f"LOG: {event}",
            "score": 0.3,
            "value": 0.0
        }


class RevenuePlugin:
    def handle(self, event):
        return {
            "output": "revenue tracking active",
            "score": 0.4,
            "value": 0.0
        }
