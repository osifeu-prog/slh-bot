#!/data/data/com.termux/files/usr/bin/bash

echo "🧠 Installing SWARM OS V13 FULL (CLEAN TERMUX BUILD)..."

mkdir -p slh_clean/slh_v9
cd slh_clean/slh_v9

cat > swarm.py << 'PY'
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
# SWARM CORE V13 (STABLE + ROADMAP)
# =========================

class SwarmV13:

    def __init__(self):
        self.agents = {}
        self.reputation = {}
        self.policy = {}
        self.user_memory = {}

        self.db = sqlite3.connect("swarm.db", check_same_thread=False)
        self._db()

        self.pool = ThreadPoolExecutor(max_workers=4)

        print("🧠 SWARM V13 ONLINE (TERMUX READY)")

        self.roadmap = [
            {"id":1,"task":"telegram gateway","done":False},
            {"id":2,"task":"memory system","done":False},
            {"id":3,"task":"plugin engine","done":False},
            {"id":4,"task":"learning system","done":False},
            {"id":5,"task":"revenue tracking","done":False}
        ]

    # DB
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

    # REGISTER
    def register(self, name, agent):
        self.agents[name] = agent
        self.reputation[name] = 1.0
        self.policy[name] = 1.0
        print("✅", name)

    # SCORE
    def score(self, name, r):
        return r["score"] * self.reputation[name] * self.policy[name]

    # EXEC
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

    # SWARM
    def swarm(self, user, cmd):

        event = {"cmd": cmd, "user": user}

        results = [self._run(n,a,event) for n,a in self.agents.items()]

        winner = max(results, key=lambda x: x["final"])

        self._learn(winner)
        self._save(user, cmd, winner)

        return {
            "user": user,
            "winner": winner,
            "roadmap": self.roadmap,
            "all": results
        }

    # LEARN
    def _learn(self, w):
        n = w["agent"]
        self.reputation[n] = self.reputation[n]*0.93 + w["final"]*0.07

    # SAVE
    def _save(self, user, cmd, winner):
        cur = self.db.cursor()
        cur.execute(
            "INSERT INTO memory VALUES (?,?,?,?,?)",
            (time.time(), user, cmd, winner["agent"], winner["final"])
        )
        self.db.commit()

        self.user_memory.setdefault(user, []).append(cmd)

    # ROUTER
    def route(self, user, cmd):

        if cmd == "/roadmap":
            return self.roadmap

        if cmd == "memory":
            return self.user_memory.get(user, [])

        return self.swarm(user, cmd)

    # LOOP
    def loop(self):

        print("\n🚀 SWARM READY (TERMUX)\nformat: user:message\n")

        while True:
            raw = input(">>> ").strip()

            if raw == "exit":
                break

            if ":" not in raw:
                print("format: user:message")
                continue

            user, cmd = raw.split(":",1)

            result = self.route(user, cmd)

            print("\n📡 RESULT:\n")
            print(json.dumps(result, indent=2))


# BOOT
os = SwarmV13()

os.register("telegram", TelegramAgent())
os.register("smart", SmartAgent())
os.register("analytics", AnalyticsAgent())

os.loop()
PY

python swarm.py

