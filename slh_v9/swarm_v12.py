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
            return {"output":"pong","score":0.96,"value":0.01}
        return {"output":"tg:"+cmd,"score":0.6,"value":0}


class SmartAgent:
    def handle(self, e):
        cmd = e["cmd"]
        score = 0.93 if "telegram" in cmd else 0.55
        return {"output":"smart:"+cmd,"score":score,"value":0}


class AnalyticsAgent:
    def handle(self, e):
        return {"output":"analytics:"+e["cmd"],"score":0.58,"value":0}


# =========================
# V12 SWARM OS + ROADMAP ENGINE
# =========================

class SwarmV12:

    def __init__(self):
        self.agents = {}
        self.reputation = {}
        self.policy = {}

        self.user_memory = {}
        self.roadmap = []

        self.db = sqlite3.connect("swarm_v12.db", check_same_thread=False)
        self._db()

        self.pool = ThreadPoolExecutor(max_workers=6)

        print("🧠 V12 SWARM + TELEGRAM GATEWAY READY")

        self._init_roadmap()

    # ---------------- DB ----------------
    def _db(self):
        cur = self.db.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS memory (
            ts REAL,
            user TEXT,
            cmd TEXT,
            winner TEXT,
            score REAL
        )
        """)
        self.db.commit()

    # ---------------- ROADMAP ENGINE ----------------
    def _init_roadmap(self):
        self.roadmap = [
            {"id": 1, "task": "Telegram webhook integration", "status": "pending"},
            {"id": 2, "task": "User session memory", "status": "pending"},
            {"id": 3, "task": "Plugin hot execution", "status": "pending"},
            {"id": 4, "task": "Revenue tracking per user", "status": "pending"},
            {"id": 5, "task": "Agent routing optimization", "status": "pending"},
        ]

    def roadmap_status(self):
        return {
            "roadmap": self.roadmap,
            "progress": f"{sum(1 for t in self.roadmap if t['status']=='done')}/{len(self.roadmap)}"
        }

    def complete_task(self, task_id):
        for t in self.roadmap:
            if t["id"] == task_id:
                t["status"] = "done"
                return t

    # ---------------- REGISTER ----------------
    def register(self, name, agent):
        self.agents[name] = agent
        self.reputation[name] = 1.0
        self.policy[name] = 1.0
        print("✅", name)

    # ---------------- USER MEMORY ----------------
    def remember_user(self, user, cmd, result):
        if user not in self.user_memory:
            self.user_memory[user] = []

        self.user_memory[user].append({
            "cmd": cmd,
            "result": result,
            "ts": time.time()
        })

        if len(self.user_memory[user]) > 50:
            self.user_memory[user].pop(0)

    # ---------------- SCORE ----------------
    def score(self, name, r):
        return r["score"] * self.reputation[name] * self.policy[name]

    # ---------------- EXEC ----------------
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

    # ---------------- SWARM ----------------
    async def swarm(self, user, cmd):

        event = {"cmd": cmd, "user": user}

        loop = asyncio.get_event_loop()

        futures = [
            loop.run_in_executor(self.pool, self._run, name, agent, event)
            for name, agent in self.agents.items()
        ]

        results = await asyncio.gather(*futures)

        winner = max(results, key=lambda x: x["final"])

        self.remember_user(user, cmd, winner)

        self._save(user, cmd, winner)

        return {
            "user": user,
            "winner": winner,
            "all": results
        }

    # ---------------- SAVE ----------------
    def _save(self, user, cmd, winner):
        cur = self.db.cursor()
        cur.execute(
            "INSERT INTO memory VALUES (?,?,?,?,?)",
            (time.time(), user, cmd, winner["agent"], winner["final"])
        )
        self.db.commit()

    # ---------------- ROUTE ----------------
    async def route(self, user, cmd):

        if cmd == "/roadmap":
            return self.roadmap_status()

        if cmd.startswith("/done"):
            try:
                task_id = int(cmd.split(" ")[1])
                return self.complete_task(task_id)
            except:
                return {"error":"usage /done <id>"}

        if cmd == "memory":
            return self.user_memory.get(user, [])

        return await self.swarm(user, cmd)

    # ---------------- LOOP (SIM TELEGRAM GATEWAY) ----------------
    async def loop(self):

        print("\n🚀 V12 TELEGRAM GATEWAY READY\n")

        while True:
            raw = input("You (user:msg): ").strip()

            if raw == "exit":
                break

            if ":" not in raw:
                print("format: user:message")
                continue

            user, cmd = raw.split(":", 1)

            result = await self.route(user, cmd)

            print("\n📡 RESULT:\n")
            print(json.dumps(result, indent=2))


# =========================
# BOOT
# =========================

os = SwarmV12()

os.register("telegram", TelegramAgent())
os.register("smart", SmartAgent())
os.register("analytics", AnalyticsAgent())

asyncio.run(os.loop())
