class Dispatcher:
    def __init__(self, kernel):
        self.kernel = kernel

    def dispatch(self, event):
        cmd = event.get("cmd")

        if not cmd:
            return {
                "type": "error",
                "data": "missing cmd"
            }

        if cmd == "status":
            return {
                "type": "system",
                "data": self.kernel.status()
            }

        if cmd == "agents":
            return {
                "type": "system",
                "data": self.kernel.status()
            }

        if ":" in cmd:
            name, real_cmd = cmd.split(":", 1)
            return self.kernel.call_agent(name, real_cmd, event)

        return self.kernel.call_default(event)
