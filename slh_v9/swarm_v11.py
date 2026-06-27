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
        return {"output":"tg:"+cmd,"score":0.6,"value":0}


class SmartAgent:
    def handle(self, e):
        cmd = e["cmd"]
        score = 0.92 if "telegram" in cmd else 0.55
        return {"output":"smart:"+cmd,"score":score,"value":0}


class AnalyticsAgent:
    def handle(self, e):
        return {"output":"analytics:"+e["cmd"],"score":0.58,"value":0}


# =========================
# V11 EVENT STREAM KERNEL
# =========================

class SwarmV11:

    def __init__(self):
        self.agents = {}
        self.reputation = {}
        self.policy = {}

        self.queue = asyncio.Queue()

        self.db = sqlite3.connect("swarm_v11.db", check_same_thread=False)
        self._db()

        self.pool = ThreadPoolExecutor(max_workers=6)

        print("🧠 V11 AI OS KERNEL ONLINE")

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

    # ---------- SCORE ----------
    def score(self, name, r):
        return r["score"] * self.reputation[name] * self.policy[name]

    # ---------- EXEC ----------
    def _run(self, name, agent, event):
        try:
            r = agent.handle(event)

            if not isinstance(r, dict):
                r = {"output":r,"score":0.5,"value":0}

            r["agent"] = name
            r["final"] = self.score(name, r)

            return r

        except Exception as e:
            return {"agent":name,"output":str(e),"score":0,"final":0,"value":0}

    # ---------- SWARM ----------
    async def swarm(self, cmd):

        event = {"cmd": cmd, "ts": time.time()}

        loop = asyncio.get_event_loop()

        futures = [
            loop.run_in_executor(self.pool, self._run, name, agent, event)
            for name, agent in self.agents.items()
        ]

        results = await asyncio.gather(*futures)

        winner = max(results, key=lambda x: x["final"])

        self._learn(winner)
        self._save(cmd, winner)

        return {
            "winner": winner,
            "all": results,
            "revenue_signal": winner["value"]
        }

    # ---------- LEARN ----------
    def _learn(self, w):
        n = w["agent"]
        self.reputation[n] = self.reputation[n]*0.91 + w["final"]*0.09

        for k in self.policy:
            self.policy[k] *= 1.0 if k == n else 0.997

    # ---------- MEMORY ----------
    def _save(self, cmd, w):
        cur = self.db.cursor()
        cur.execute(
            "INSERT INTO memory VALUES (?,?,?,?)",
            (time.time(), cmd, w["agent"], w["final"])
        )
        self.db.commit()

    # ---------- EVENT EMITTER ----------
    async def emit(self, cmd):
        await self.queue.put(cmd)

    # ---------- STREAM LOOP ----------
    async def stream(self):

        print("\n🚀 V11 STREAM KERNEL RUNNING\n")

        while True:
            cmd = await self.queue.get()
            result = await self.swarm(cmd)

            print("\n📡 STREAM EVENT RESULT:\n")
            print(json.dumps(result, indent=2))

    # ---------- CLI FEED ----------
    async def cli(self):

        while True:
            cmd = input("You: ").strip()
            if cmd == "exit":
                break

            await self.emit(cmd)

    # ---------- BOOT ----------
    async def run(self):

        self.register("telegram", TelegramAgent())
        self.register("smart", SmartAgent())
        self.register("analytics", AnalyticsAgent())

        await asyncio.gather(
            self.stream(),
            self.cli()
        )


# =========================
# START
# =========================

if __name__ == "__main__":
    asyncio.run(SwarmV11().run())
