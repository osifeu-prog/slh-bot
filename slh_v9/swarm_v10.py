import asyncio
import time
import sqlite3
import json
from concurrent.futures import ThreadPoolExecutor


# =========================
# AGENTS
# =========================

class TelegramAgent:
    def handle(self, e):
        cmd = e["cmd"]
        if "ping" in cmd:
            return {"output":"pong","score":0.95,"value":0.01}
        return {"output":"telegram:"+cmd,"score":0.6,"value":0}


class SmartAgent:
    def handle(self, e):
        cmd = e["cmd"]
        score = 0.9 if "telegram" in cmd else 0.55
        return {"output":"smart:"+cmd,"score":score,"value":0}


class AnalyticsAgent:
    def handle(self, e):
        return {"output":"analytics:"+e["cmd"],"score":0.58,"value":0}


# =========================
# SWARM V10 CORE
# =========================

class SwarmV10:

    def __init__(self):
        self.agents = {}
        self.reputation = {}
        self.policy = {}

        self.memory_cache = []

        self.revenue = 0.0

        self.plugins = {}
        self.mailbox = {}

        self.db = sqlite3.connect("swarm_v10.db", check_same_thread=False)
        self._init_db()

        self.pool = ThreadPoolExecutor(max_workers=6)

        print("🧠 SWARM V10 EVENT OS ONLINE")

    # ---------------- DB ----------------
    def _init_db(self):
        cur = self.db.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS memory (
            ts REAL,
            cmd TEXT,
            winner TEXT,
            score REAL
        )
        """)
        self.db.commit()

    # ---------------- REGISTER ----------------
    def register(self, name, agent):
        self.agents[name] = agent
        self.reputation[name] = 1.0
        self.policy[name] = 1.0
        self.mailbox[name] = []
        print("✅ agent:", name)

    # ---------------- PLUGINS ----------------
    def register_plugin(self, name, fn):
        self.plugins[name] = fn
        print("🔌 plugin:", name)

    def run_plugin(self, name, data):
        if name in self.plugins:
            return self.plugins[name](data)
        return None

    # ---------------- MESSAGE BUS ----------------
    def send(self, to, msg):
        if to in self.mailbox:
            self.mailbox[to].append(msg)

    def receive(self, name):
        return self.mailbox.get(name, [])

    # ---------------- SCORE ----------------
    def score(self, name, r):
        return r["score"] * self.reputation[name] * self.policy[name]

    # ---------------- EXEC AGENT ----------------
    def _run(self, name, agent, event):
        try:
            r = agent.handle(event)

            if not isinstance(r, dict):
                r = {"output":r,"score":0.5,"value":0}

            r["agent"] = name
            r["final"] = self.score(name, r)

            return r

        except Exception as e:
            return {
                "agent": name,
                "output": str(e),
                "score": 0,
                "final": 0,
                "value": 0
            }

    # ---------------- SWARM (PARALLEL VOTING) ----------------
    def swarm(self, cmd):

        event = {"cmd": cmd, "ts": time.time()}

        futures = [
            self.pool.submit(self._run, name, agent, event)
            for name, agent in self.agents.items()
        ]

        results = []

        for f in futures:
            try:
                results.append(f.result(timeout=2))
            except:
                results.append({
                    "agent": "timeout",
                    "output": "timeout",
                    "score": 0,
                    "final": 0,
                    "value": 0
                })

        winner = max(results, key=lambda x: x["final"])

        self.revenue += winner["value"]

        self._learn(winner)
        self._save(cmd, winner)

        explanation = {
            "winner_agent": winner["agent"],
            "reason": "highest final score = score * reputation * policy",
            "score": winner["final"]
        }

        return {
            "winner": winner,
            "explanation": explanation,
            "all": results
        }

    # ---------------- LEARNING ----------------
    def _learn(self, winner):
        w = winner["agent"]
        self.reputation[w] = self.reputation[w]*0.92 + winner["final"]*0.08

    # ---------------- MEMORY ----------------
    def _save(self, cmd, winner):
        cur = self.db.cursor()
        cur.execute(
            "INSERT INTO memory VALUES (?,?,?,?)",
            (time.time(), cmd, winner["agent"], winner["final"])
        )
        self.db.commit()

        self.memory_cache.append({
            "cmd": cmd,
            "winner": winner["agent"],
            "score": winner["final"]
        })

        if len(self.memory_cache) > 200:
            self.memory_cache.pop(0)

    def memory(self, limit=5):
        cur = self.db.cursor()
        cur.execute("SELECT * FROM memory ORDER BY ts DESC LIMIT ?", (limit,))
        return cur.fetchall()

    # ---------------- ROUTER ----------------
    def route(self, cmd):

        if cmd == "status":
            return {
                "agents": list(self.agents.keys()),
                "revenue": self.revenue,
                "reputation": self.reputation
            }

        if cmd == "memory":
            return self.memory()

        if cmd.startswith("plugin:"):
            name = cmd.split(":")[1]
            return self.run_plugin(name, cmd)

        if cmd.startswith("send:"):
            _, to, msg = cmd.split(":", 2)
            self.send(to, msg)
            return {"sent_to": to, "msg": msg}

        if cmd.startswith("inbox:"):
            name = cmd.split(":")[1]
            return self.receive(name)

        return self.swarm(cmd)

    # ---------------- LOOP ----------------
    def loop(self):

        print("\n🚀 V10 SWARM OS READY\n")

        while True:
            cmd = input("You: ").strip()
            if cmd == "exit":
                break

            result = self.route(cmd)

            print("\n📡 RESULT:\n")
            print(json.dumps(result, indent=2))


# =========================
# BOOT
# =========================

os = SwarmV10()

os.register("telegram", TelegramAgent())
os.register("smart", SmartAgent())
os.register("analytics", AnalyticsAgent())

# plugin example
os.register_plugin("echo", lambda x: {"echo": x, "ts": time.time()})

os.loop()
