import time
from queue import Queue
import threading


class SLHV4Kernel:

    def __init__(self):
        self.agents = {}
        self.events = Queue()
        self.revenue = 0.0

        print("🧠 SLH V4 AGENT OS BOOTED")

    # ---------------- REGISTER AGENT ----------------
    def register(self, name, agent):
        self.agents[name] = agent
        print(f"✅ agent registered: {name}")

    # ---------------- EMIT ----------------
    def emit(self, event):
        event["timestamp"] = time.time()
        self.events.put(event)

    # ---------------- CORE ROUTE ----------------
    def route(self, event):

        cmd = event.get("cmd", "")
        module = cmd.split(":")[0]

        agent = self.agents.get(module)
        if not agent:
            return {"output": "❌ no agent", "score": 0}

        result = agent.handle(event)

        # normalize output
        if isinstance(result, str):
            result = {"output": result, "score": 0.5, "value": 0.0}

        self.revenue += result.get("value", 0.0)

        return result

    # ---------------- PARALLEL EXECUTION ----------------
    def run_parallel(self, event):
        results = []

        threads = []

        for name, agent in self.agents.items():

            def run(a=agent):
                res = a.handle(event)

                if isinstance(res, str):
                    res = {"output": res, "score": 0.5, "value": 0.0}

                results.append(res)

            t = threading.Thread(target=run)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # pick best
        best = max(results, key=lambda x: x.get("score", 0))
        return best

    # ---------------- LOOP ----------------
    def loop(self):
        while True:
            if not self.events.empty():
                event = self.events.get()

                result = self.run_parallel(event)

                self.revenue += result.get("value", 0.0)

                print("➡️ RESULT:", result)

            time.sleep(0.1)

    def start(self):
        t = threading.Thread(target=self.loop, daemon=True)
        t.start()

        while True:
            time.sleep(1)
