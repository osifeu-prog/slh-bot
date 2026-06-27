import asyncio
import time
import sqlite3
import json
import math
from concurrent.futures import ThreadPoolExecutor


# =========================
# AGENTS
# =========================

class BaseAgent:
    def handle(self, event):
        return {"output":"base","score":0.5,"value":0}


class TelegramAgent(BaseAgent):
    def handle(self, e):
        cmd = e["cmd"]
        if "ping" in cmd:
            return {"output":"pong","score":0.97,"value":0.01}
        return {"output":f"tg:{cmd}","score":0.6,"value":0}


class SmartAgent(BaseAgent):
    def handle(self, e):
        cmd = e["cmd"]
        score = 0.9 if "telegram" in cmd else 0.55
        return {"output":f"smart:{cmd}","score":score,"value":0}


class AnalyticsAgent(BaseAgent):
    def handle(self, e):
        return {"output":f"analytics:{e['cmd']}","score":0.58,"value":0}


# =========================
# SWARM OS V9.5
# =========================

class SwarmV95:

    def __init__(self):
        self.agents = {}
        self.reputation = {}
        self.policy = {}

        self.memory = []
        self.revenue = 0.0

        self.db = sqlite3.connect("swarm_v95.db")
        self._db()

        self.pool = ThreadPoolExecutor(max_workers=5)

        print("🧠 SWARM OS V9.5 ONLINE")

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
        print("✅", name)

    # ---------- EXEC AGENT (parallel) ----------
    def _exec(self, name, agent, event):
        r = agent.handle(event)

        if not isinstance(r, dict):
            r = {"output":r,"score":0.5,"value":0}

        rep = self.reputation[name]

        r["agent"] = name
        r["final"] = r["score"] * rep

        return r

    async def swarm(self, cmd):

        event = {"cmd": cmd}

        loop = asyncio.get_event_loop()

        tasks = [
            loop.run_in_executor(self.pool, self._exec, name, agent, event)
            for name, agent in self.agents.items()
        ]

        results = await asyncio.gather(*tasks)

        # 🧠 weighted consensus (not just max)
        total = sum(r["final"] for r in results)
        winner = max(results, key=lambda x: x["final"])

        confidence = winner["final"] / (total + 1e-9)

        self.revenue += winner["value"]

        self._learn(winner, confidence)
        self._save(cmd, winner, confidence)

        return {
            "winner": winner,
            "confidence": confidence,
            "all": results
        }

    # ---------- LEARNING ----------
    def _learn(self, winner, conf):
        w = winner["agent"]

        self.reputation[w] = self.reputation[w]*0.9 + conf*0.1

    # ---------- MEMORY ----------
    def _save(self, cmd, winner, conf):
        cur = self.db.cursor()
        cur.execute(
            "INSERT INTO memory VALUES (?,?,?,?)",
            (time.time(), cmd, winner["agent"], conf)
        )
        self.db.commit()

    def recall(self, limit=5):
        cur = self.db.cursor()
        cur.execute("SELECT * FROM memory ORDER BY ts DESC LIMIT ?", (limit,))
        return cur.fetchall()

    # ---------- ROUTER ----------
    async def route(self, cmd):

        if cmd == "status":
            return {
                "agents": list(self.agents.keys()),
                "revenue": self.revenue,
                "reputation": self.reputation
            }

        if cmd == "memory":
            return self.recall()

        return await self.swarm(cmd)

    # ---------- LOOP ----------
    async def loop(self):

        print("\n🚀 V9.5 SWARM READY\n")

        while True:
            cmd = input("You: ").strip()
            if cmd == "exit":
                break

            res = await self.route(cmd)

            print("\n📡 RESULT:\n")
            print(json.dumps(res, indent=2))


# =========================
# BOOT
# =========================

os = SwarmV95()

os.register("telegram", TelegramAgent())
os.register("smart", SmartAgent())
os.register("analytics", AnalyticsAgent())

asyncio.run(os.loop())
