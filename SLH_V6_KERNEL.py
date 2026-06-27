import time
from queue import Queue
import threading


class SLHV6Kernel:

    def __init__(self):
        self.agents = {}
        self.events = Queue()

        self.revenue = 0.0

        # 🧠 MEMORY + LEARNING
        self.memory = []
        self.reputation = {}

        print("🧠 SLH V6 MEMORY KERNEL BOOTED")

    # ---------------- REGISTER ----------------
    def register(self, name, agent):
        self.agents[name] = agent
        self.reputation[name] = 1.0
        print(f"✅ agent registered: {name}")

    # ---------------- MEMORY ----------------
    def remember(self, record):
        self.memory.append(record)

        # keep memory bounded
        if len(self.memory) > 200:
            self.memory.pop(0)

    # ---------------- EMIT ----------------
    def emit(self, event):
        event["timestamp"] = time.time()
        self.events.put(event)

    # ---------------- CONSENSUS 2.0 ----------------
    def run_consensus(self, event):
        results = []

        for name, agent in self.agents.items():
            res = agent.handle(event)

            if isinstance(res, str):
                res = {"output": res, "score": 0.5, "value": 0.0}

            rep = self.reputation.get(name, 1.0)

            # 🧠 weighted score
            res["final_score"] = res["score"] * rep
            res["agent"] = name
            res["reputation"] = rep

            results.append(res)

        best = max(results, key=lambda x: x["final_score"])

        # 💰 update revenue
        self.revenue += best.get("value", 0.0)

        # 🧠 update reputation
        self.update_reputation(best["agent"], best["final_score"])

        # 🧠 store memory
        self.remember({
            "event": event,
            "winner": best,
            "all": results,
            "timestamp": time.time()
        })

        return {
            "winner": best,
            "all": results
        }

    # ---------------- REPUTATION UPDATE ----------------
    def update_reputation(self, agent_name, score):
        old = self.reputation.get(agent_name, 1.0)

        # learning rate
        new = old * 0.9 + score * 0.1

        self.reputation[agent_name] = new

    # ---------------- ROUTE ----------------
    def route(self, event):
        cmd = event.get("cmd", "")

        if cmd == "status":
            return {
                "agents": list(self.agents.keys()),
                "revenue": self.revenue,
                "reputation": self.reputation
            }

        if cmd == "memory":
            return self.memory[-5:]

        return self.run_consensus(event)

    # ---------------- LOOP ----------------
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
