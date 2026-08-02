class EchoAgent:
    def process(self, event):
        return {
            "echo": event.get("cmd"),
            "source": event.get("source")
        }
