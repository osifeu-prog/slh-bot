import asyncio
import time
import sqlite3
import json
import math


# =========================
# AGENTS
# =========================

class TelegramAgent:
    def handle(self, e):
        cmd = e["cmd"]
        if "ping" in cmd:
            return {"output":"pong", "score":0.95, "value":0.01}
        return {"output":f"tg:{cmd}", "score":0.6, "value":0}


class SmartAgent:
    def handle(self, e):
        cmd = e["cmd"]
        score = 0.88 if "telegram" in cmd else 0.52
        return {"output":f"smart:{cmd}", "score":score, "value":0}


class AnalyticsAgent:
    def handle(self, e):
        return {"output":f"analytics:{e['cmd']}", "score":0.55, "value":0}


# =========================
# SWARM OS CORE
# =========================

class SwarmOS:

    def __init__(self):
        self.agents = {}
        self.plugins = {}

        self.reputation = {}
        self.policy = {}
        self.revenue = 0.0

        self.db = sqlite3.connect("swarm_os.db")
        self._db()

        print("🧠 SWARM OS V8.1 ONLINE")

    # ---------- DB ----------
    def _db(self):
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

    # ---------- REGISTER ----------
    def register(self, name, agent):
        self.agents[name] = agent
        self.reputation[name] = 1.0
        self.policy[name] = 1.0
        print("✅ agent:", name)

    # ---------- PLUGINS ----------
    def register_plugin(self, name, fn):
        self.plugins[name] = fn
        print("🔌 plugin:", name)

    def run_plugin(self, name, data):
        if name in self.plugins:
            return self.plugins[name](data)
        return None

    # ---------- SCORE ----------
    def score(self, name, r):
        return r["score"] * self.reputation[name] * self.policy[name]

    # ---------- VOTING ----------
    async def run_agent(self, name, agent, event):
        r = agent.handle(event)
        r["agent"] = name
        r["final"] = self.score(name, r)
        return r

    async def swarm(self, cmd):

        event = {"cmd": cmd}

        results = await asyncio.gather(*[
            self.run_agent(n,a,event)
            for n,a in self.agents.items()
        ])

        winner = max(results, key=lambda x:x["final"])

        self.revenue += winner["value"]

        self._learn(winner)
        self._save(cmd, winner)

        return {
            "winner": winner,
            "all": results
        }

    # ---------- LEARN ----------
    def _learn(self, w):
        n = w["agent"]
        self.reputation[n] = self.reputation[n]*0.9 + w["final"]*0.1

        for k in self.policy:
            self.policy[k] *= 1.01 if k == n else 0.995

    # ---------- MEMORY ----------
    def _save(self, cmd, w):
        cur = self.db.cursor()
        cur.execute(
            "INSERT INTO memory VALUES (?,?,?,?)",
            (time.time(), cmd, w["agent"], w["final"])
        )
        self.db.commit()

    def memory(self, limit=5):
        cur = self.db.cursor()
        cur.execute("SELECT * FROM memory ORDER BY ts DESC LIMIT ?", (limit,))
        return cur.fetchall()

    # ---------- ROUTER ----------
    async def route(self, cmd):

        if cmd == "status":
            return {
                "agents": list(self.agents.keys()),
                "revenue": self.revenue,
                "reputation": self.reputation,
                "policy": self.policy
            }

        if cmd.startswith("memory"):
            return self.memory()

        if cmd.startswith("plugin:"):
            name = cmd.split(":")[1]
            return self.run_plugin(name, cmd)

        return await self.swarm(cmd)

    # ---------- LOOP ----------
    async def loop(self):

        print("\n🚀 SWARM OS READY\n(type exit to quit)\n")

        while True:
            cmd = input("You: ").strip()
            if cmd == "exit":
                break

            result = await self.route(cmd)

            print("\n📡 RESULT:\n")
            print(json.dumps(result, indent=2))


# =========================
# BOOT SYSTEM
# =========================

os = SwarmOS()

os.register("telegram", TelegramAgent())
os.register("smart", SmartAgent())
os.register("analytics", AnalyticsAgent())

# plugin example
os.register_plugin("echo", lambda x: {"echo": x, "ts": time.time()})

asyncio.run(os.loop())
