import time
from queue import Queue
import threading


class SLHV7Kernel:

    def __init__(self):
        self.agents = {}
        self.events = Queue()
        self.revenue = 0.0
        self.memory = []
        self.reputation = {}

        print("🧠 SLH V7 BOOTED")

    def register(self, name, agent):
        self.agents[name] = agent
        self.reputation[name] = 1.0
        print(f"✅ agent registered: {name}")

    def remember(self, record):
        self.memory.append(record)
        if len(self.memory) > 300:
            self.memory.pop(0)

    def emit(self, event):
        event["timestamp"] = time.time()
        self.events.put(event)

    def run_consensus(self, event):

        results = []

        for name, agent in self.agents.items():
            res = agent.handle(event)

            if isinstance(res, str):
                res = {"output": res, "score": 0.5, "value": 0.0}

            rep = self.reputation.get(name, 1.0)

            final_score = res["score"] * rep

            res.update({
                "agent": name,
                "reputation": rep,
                "final_score": final_score
            })

            results.append(res)

        best = max(results, key=lambda x: x["final_score"])

        self.revenue += best.get("value", 0.0)

        self.remember({
            "event": event,
            "winner": best,
            "all": results,
            "ts": time.time()
        })

        return {
            "winner": best,
            "all": results
        }

    def route(self, event):

        cmd = event.get("cmd", "")

        if cmd == "status":
            return {
                "agents": list(self.agents.keys()),
                "revenue": self.revenue,
                "reputation": self.reputation
            }

        if cmd == "memory":
            return self.memory[-10:]

        return self.run_consensus(event)
