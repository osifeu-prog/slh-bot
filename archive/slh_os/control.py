class ControlLayer:

    def __init__(self, core):
        self.core = core

    # החלטות מערכת
    def route(self, event):
        etype = event.get("type")

        if etype == "memory_save":
            self.core.save(event["key"], event["value"])
            return "saved"

        if etype == "memory_load":
            return self.core.load(event["key"])

        if etype == "agent_spawn":
            return self.spawn_agent(event)

        return "unknown_event"

    # בסיס לאג'נטים (שלב הבא נרחיב)
    def spawn_agent(self, event):
        name = event.get("name", "anon")
        self.core.agents[name] = {
            "status": "active",
            "tasks": []
        }
        return f"agent {name} created"
