import time
from queue import Queue
import threading


class SLHV5Kernel:

    def __init__(self):
        self.agents = {}
        self.events = Queue()
        self.revenue = 0.0

        print("🧠 SLH V5 BOOTED")

    def register(self, name, agent):
        self.agents[name] = agent
        print(f"✅ agent registered: {name}")

    def emit(self, event):
        event["timestamp"] = time.time()
        self.events.put(event)

    def run_consensus(self, event):
        results = []

        for name, agent in self.agents.items():
            res = agent.handle(event)

            if isinstance(res, str):
                res = {"output": res, "score": 0.5, "value": 0.0}

            res["agent"] = name
            results.append(res)

        best = max(results, key=lambda x: x["score"])
        self.revenue += best.get("value", 0.0)

        return {
            "winner": best,
            "all": results
        }

    def route(self, event):
        cmd = event.get("cmd", "")

        if cmd == "status":
            return {
                "agents": list(self.agents.keys()),
                "revenue": self.revenue
            }

        return self.run_consensus(event)

    def loop(self):
        while True:
            if not self.events.empty():
                event = self.events.get()
                result = self.route(event)
                print("🏁 RESULT:", result)

            time.sleep(0.1)

    def start(self):
        t = threading.Thread(target=self.loop, daemon=True)
        t.start()

        while True:
            time.sleep(1)
