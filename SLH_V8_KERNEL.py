import time
import threading
from queue import Queue


class SLHV8Kernel:

    def __init__(self):
        self.agents = {}
        self.plugins = {}

        self.events = Queue()

        self.memory = []
        self.reputation = {}
        self.revenue = 0.0

        print("🧠 SLH V8 SWARM KERNEL BOOTED")

    # ---------------- REGISTER AGENT ----------------
    def register_agent(self, name, agent):
        self.agents[name] = agent
        self.reputation[name] = 1.0
        print(f"✅ agent registered: {name}")

    # ---------------- PLUGIN SYSTEM ----------------
    def register_plugin(self, name, plugin):
        self.plugins[name] = plugin
        print(f"🔌 plugin loaded: {name}")

    def run_plugin(self, name, event):
        if name in self.plugins:
            return self.plugins[name].handle(event)
        return None

    # ---------------- MEMORY ----------------
    def remember(self, record):
        self.memory.append(record)
        if len(self.memory) > 500:
            self.memory.pop(0)

    # ---------------- EVENT BUS ----------------
    def emit(self, event):
        event["ts"] = time.time()
        self.events.put(event)

    def event_loop(self):
        while True:
            if not self.events.empty():
                event = self.events.get()
                result = self.route(event)
                print("📡 EVENT RESULT:", result)

            time.sleep(0.05)

    # ---------------- PARALLEL EXECUTION ----------------
    def run_parallel(self, event):
        results = []
        threads = []

        def run_agent(name, agent):
            try:
                res = agent.handle(event)

                if isinstance(res, str):
                    res = {"output": res, "score": 0.5, "value": 0.0}

                rep = self.reputation.get(name, 1.0)

                res["agent"] = name
                res["score"] = res["score"] * rep

                results.append(res)

            except Exception as e:
                results.append({
                    "agent": name,
                    "output": str(e),
                    "score": 0.0,
                    "value": 0.0
                })

        for name, agent in self.agents.items():
            t = threading.Thread(target=run_agent, args=(name, agent))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        return results

    # ---------------- CONSENSUS VOTING ----------------
    def consensus(self, event):

        results = self.run_parallel(event)

        winner = max(results, key=lambda x: x["score"])

        self.revenue += winner.get("value", 0.0)

        # learning
        self.update_reputation(winner["agent"], winner["score"])

        # memory reasoning
        self.remember({
            "event": event,
            "winner": winner,
            "all": results
        })

        return {
            "winner": winner,
            "all": results
        }

    # ---------------- REPUTATION ----------------
    def update_reputation(self, agent, score):
        old = self.reputation.get(agent, 1.0)
        self.reputation[agent] = old * 0.9 + score * 0.1

    # ---------------- ROUTER ----------------
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

        if cmd.startswith("plugin:"):
            name = cmd.split(":")[1]
            return self.run_plugin(name, event)

        return self.consensus(event)

    # ---------------- START ----------------
    def start(self):
        t = threading.Thread(target=self.event_loop, daemon=True)
        t.start()
        print("🚀 V8 EVENT BUS RUNNING")

        while True:
            time.sleep(1)
