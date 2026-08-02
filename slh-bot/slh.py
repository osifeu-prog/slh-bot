import time
import subprocess
import threading
import uuid
from queue import Queue

# =========================
# JOURNAL (TRACE LAYER)
# =========================
class Journal:
    def log(self, msg):
        print(f"[JOURNAL] {msg}")

J = Journal()

# =========================
# EXEC SAFE LAYER
# =========================
class Exec:
    def run(self, cmd):
        J.log(f"RUN: {cmd}")
        try:
            return subprocess.getoutput(cmd)
        except Exception as e:
            return str(e)

# =========================
# CONTROLLER (TERMUX OPS)
# =========================
class Controller:
    def __init__(self):
        self.exec = Exec()

    def status(self):
        return self.exec.run("ps aux | grep python | grep -v grep")

    def clean(self):
        self.exec.run("pkill -f python")
        return "cleaned"

    def test(self):
        return self.exec.run("python3 --version")

# =========================
# AGENT CORE
# =========================
class Agent:
    def __init__(self, name):
        self.name = name
        self.q = Queue()
        self.running = True

    def loop(self):
        while self.running:
            if not self.q.empty():
                task = self.q.get()
                J.log(f"[{self.name}] TASK: {task}")
            time.sleep(0.3)

# =========================
# CONTRACT SYSTEM (MINIMAL)
# =========================
class ContractEngine:
    def __init__(self):
        self.db = {}

    def create(self, ctype):
        cid = str(uuid.uuid4())
        self.db[cid] = {
            "type": ctype,
            "status": "created",
            "ts": time.time()
        }
        J.log(f"CONTRACT CREATED {cid}")
        return cid

    def update(self, cid, status):
        if cid in self.db:
            self.db[cid]["status"] = status
            self.db[cid]["updated"] = time.time()
            J.log(f"CONTRACT {cid} -> {status}")

# =========================
# CORE ENGINE
# =========================
class SLH:
    def __init__(self):
        self.controller = Controller()
        self.contracts = ContractEngine()
        self.agents = {}
        self.events = Queue()

        self.last_run = {}
        self.cooldown = {"status": 3}

    # ---------- EVENTS ----------
    def emit(self, event):
        self.events.put({
            "id": str(uuid.uuid4()),
            "type": event
        })

    def allowed(self, event):
        now = time.time()
        return now - self.last_run.get(event, 0) > self.cooldown.get(event, 0)

    def mark(self, event):
        self.last_run[event] = time.time()

    # ---------- AGENTS ----------
    def create_agent(self, name):
        if name in self.agents:
            return "exists"

        a = Agent(name)
        self.agents[name] = a
        threading.Thread(target=a.loop, daemon=True).start()
        return f"{name} started"

    def dispatch(self, name, task):
        if name not in self.agents:
            self.create_agent(name)
        self.agents[name].q.put(task)
        return "task queued"

    # ---------- LOOP ----------
    def loop(self):
        while True:
            if not self.events.empty():
                e = self.events.get()
                t = e["type"]

                J.log(f"EVENT {t}")

                cid = self.contracts.create(t)

                if t == "status":
                    if self.allowed(t):
                        out = self.controller.status()
                        print(out)
                        self.mark(t)
                        self.contracts.update(cid, "done")
                    else:
                        J.log("SKIP cooldown")

                elif t == "test":
                    out = self.controller.test()
                    print(out)
                    self.contracts.update(cid, "done")

                elif t.startswith("agent:"):
                    name = t.split(":")[1]
                    print(self.create_agent(name))
                    self.contracts.update(cid, "done")

            time.sleep(0.3)

    # ---------- RUN ----------
    def run(self):
        J.log("SLH vNEXT STARTED")

        threading.Thread(target=self.loop, daemon=True).start()

        # auto heartbeat
        while True:
            time.sleep(2)
            self.emit("status")


if __name__ == "__main__":
    SLH().run()
