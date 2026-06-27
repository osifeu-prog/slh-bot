import asyncio
import time
import sqlite3
import json
from queue import Queue
import math


# =========================
# AGENTS
# =========================

class TelegramAgent:
    def handle(self, event):
        cmd = event.get("cmd","")
        if "ping" in cmd:
            return {"output":"pong","score":0.95,"value":0.01}
        return {"output":f"telegram:{cmd}","score":0.6,"value":0.0}


class SmartAgent:
    def handle(self, event):
        cmd = event.get("cmd","")
        score = 0.85 if "telegram" in cmd else 0.5
        return {"output":f"smart:{cmd}","score":score,"value":0.0}


class AnalyticsAgent:
    def handle(self, event):
        return {"output":f"analytics:{event.get('cmd')}","score":0.55,"value":0.0}


# =========================
# SWARM ENGINE
# =========================

class SwarmV8:

    def __init__(self):
        self.agents = {}
        self.queue = Queue()

        self.reputation = {}
        self.policy = {}
        self.revenue = 0.0

        self.db = sqlite3.connect("swarm.db")
        self._init_db()

        print("🧠 SWARM V8 READY (TERMUX MODE)")

    def _init_db(self):
        cur = self.db.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS memory (
            ts REAL,
            event TEXT,
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

    # ---------- SCORE ----------
    def score(self, name, res):
        return res["score"] * self.reputation[name] * self.policy[name]

    def softmax(self, results):
        w = [math.exp(r["score"]) for r in results]
        s = sum(w)
        return [i/s for i in w]

    # ---------- SWARM ----------
    async def run_agent(self, name, agent, event):
        res = agent.handle(event)

        res = res if isinstance(res, dict) else {"output":res,"score":0.5,"value":0.0}

        res["agent"] = name
        res["final"] = self.score(name, res)

        return res

    async def swarm(self, cmd):
        event = {"cmd":cmd}

        results = await asyncio.gather(*[
            self.run_agent(n,a,event)
            for n,a in self.agents.items()
        ])

        winner = max(results, key=lambda x:x["final"])

        self.revenue += winner["value"]

        self.learn(winner)
        self.save(event, winner)

        return {"winner":winner,"all":results}

    # ---------- LEARN ----------
    def learn(self, winner):
        w = winner["agent"]

        self.reputation[w] = self.reputation[w]*0.92 + winner["final"]*0.08

        for k in self.policy:
            self.policy[k] *= 1.0 if k==w else 0.995

    # ---------- MEMORY ----------
    def save(self,event,winner):
        cur = self.db.cursor()
        cur.execute(
            "INSERT INTO memory VALUES (?,?,?,?)",
            (time.time(), json.dumps(event), winner["agent"], winner["final"])
        )
        self.db.commit()

    # ---------- ROUTE ----------
    async def route(self, cmd):
        if cmd == "status":
            return {
                "agents":list(self.agents.keys()),
                "revenue":self.revenue,
                "reputation":self.reputation
            }

        return await self.swarm(cmd)

    # ---------- LOOP ----------
    async def loop(self):
        print("\n🚀 TYPE COMMANDS (exit to quit)\n")

        while True:
            cmd = input("You: ").strip()
            if cmd == "exit":
                break

            result = await self.route(cmd)

            print("\n📡 RESULT:\n")
            print(json.dumps(result, indent=2))


# =========================
# BOOT
# =========================

engine = SwarmV8()

engine.register("telegram", TelegramAgent())
engine.register("smart", SmartAgent())
engine.register("analytics", AnalyticsAgent())

asyncio.run(engine.loop())
