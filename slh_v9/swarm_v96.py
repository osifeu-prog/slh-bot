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
        score = 0.9 if "telegram" in cmd else 0.55
        return {"output":"smart:"+cmd,"score":score,"value":0}


class AnalyticsAgent:
    def handle(self, e):
        return {"output":"analytics:"+e["cmd"],"score":0.58,"value":0}


# =========================
# SWARM OS CORE (FIXED)
# =========================

class SwarmOS:

    def __init__(self):
        self.agents = {}
        self.reputation = {}
        self.policy = {}
        self.revenue = 0.0

        self.db = sqlite3.connect("swarm_v96.db", check_same_thread=False)
        self._db()

        self.pool = ThreadPoolExecutor(max_workers=4)

        print("🧠 SWARM V9.6 FIXED ONLINE")

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

    # ---------- EXEC ----------
    def _run(self, name, agent, event):
        try:
            r = agent.handle(event)

            if not isinstance(r, dict):
                r = {"output":r,"score":0.5,"value":0}

            r["agent"] = name
            r["final"] = r["score"] * self.reputation[name]

            return r

        except Exception as e:
            return {"agent":name,"output":str(e),"score":0,"final":0,"value":0}

    # ---------- SWARM ----------
    def swarm(self, cmd):

        event = {"cmd": cmd}

        futures = [
            self.pool.submit(self._run, name, agent, event)
            for name, agent in self.agents.items()
        ]

        results = [f.result(timeout=5) for f in futures]

        winner = max(results, key=lambda x: x["final"])

        self.revenue += winner["value"]

        self.learn(winner)
        self.save(cmd, winner)

        return {
            "winner": winner,
            "all": results
        }

    # ---------- LEARN ----------
    def learn(self, winner):
        w = winner["agent"]
        self.reputation[w] = self.reputation[w]*0.92 + winner["final"]*0.08

    # ---------- MEMORY ----------
    def save(self, cmd, winner):
        cur = self.db.cursor()
        cur.execute(
            "INSERT INTO memory VALUES (?,?,?,?)",
            (time.time(), cmd, winner["agent"], winner["final"])
        )
        self.db.commit()

    def memory(self):
        cur = self.db.cursor()
        cur.execute("SELECT * FROM memory ORDER BY ts DESC LIMIT 5")
        return cur.fetchall()

    # ---------- ROUTER ----------
    def route(self, cmd):

        if cmd == "status":
            return {
                "agents": list(self.agents.keys()),
                "revenue": self.revenue,
                "reputation": self.reputation
            }

        if cmd == "memory":
            return self.memory()

        return self.swarm(cmd)

    # ---------- LOOP ----------
    def loop(self):

        print("\n🚀 SWARM READY (TERMUX STABLE)\n")

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

os = SwarmOS()

os.register("telegram", TelegramAgent())
os.register("smart", SmartAgent())
os.register("analytics", AnalyticsAgent())

os.loop()
