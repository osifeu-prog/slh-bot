class EchoAgent:
    def process(self, event):
        return {"echo": event.get("cmd")}
