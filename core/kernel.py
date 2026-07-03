class SLHKernel:
    def __init__(self):
        self.agents = {}
        print("🧠 KERNEL ONLINE (OS MODE v2 FINAL CORE)")

    def register(self, name, agent):
        self.agents[name] = agent
        print(f"✅ agent: {name}")

    def status(self):
        return {
            "agents": list(self.agents.keys())
        }

    def call_agent(self, name, cmd, event):
        agent = self.agents.get(name)
        if not agent:
            return {
                "type": "error",
                "data": f"unknown agent: {name}"
            }

        new_event = dict(event)
        new_event["cmd"] = cmd

        result = agent.process(new_event)

        return {
            "type": "agent",
            "data": result,
            "meta": {"agent": name}
        }

    def call_default(self, event):
        if "echo" in self.agents:
            return {
                "type": "agent",
                "data": self.agents["echo"].process(event),
                "meta": {"agent": "echo"}
            }

        return {
            "type": "error",
            "data": "no default agent"
        }
