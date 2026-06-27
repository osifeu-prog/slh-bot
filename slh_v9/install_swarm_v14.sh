#!/data/data/com.termux/files/usr/bin/bash

set -e

echo "🧠 SWARM INSTALL (V14 CLEAN TERMUX BUILD)"

# תיקייה
mkdir -p ~/slh_clean/slh_v9
cd ~/slh_clean/slh_v9

# =========================
# PYTHON FILE
# =========================
cat > swarm_v14.py << 'PY'

import time
import sqlite3
import json
from threading import Thread
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
# CORE SWARM
# =========================

class SwarmV14:
    def __init__(self):
        self.agents = {}
        self.reputation = {}
        self.policy = {}
        self.user_memory = {}

        self.db = sqlite3.connect("swarm.db", check_same_thread=False)
        self._db()

        self.pool = ThreadPoolExecutor(max_workers=4)

        print("🧠 SWARM V14 ONLINE")

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

    def register(self, name, agent):
        self.agents[name] = agent
        self.reputation[name] = 1.0
        self.policy[name] = 1.0
        print("✅", name)

    def score(self, name, r):
        return r["score"] * self.reputation[name] * self.policy[name]

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

    def swarm(self, user, cmd):
        event = {"cmd": cmd, "user": user}

        results = [self._run(n,a,event) for n,a in self.agents.items()]
        winner = max(results, key=lambda x: x["final"])

        self._save(user, cmd, winner)
        self._learn(winner)

        return {
            "user": user,
            "winner": winner,
            "all": results
        }

    def _learn(self, w):
        n = w["agent"]
        self.reputation[n] = self.reputation[n]*0.93 + w["final"]*0.07

    def _save(self, user, cmd, winner):
        cur = self.db.cursor()
        cur.execute(
            "INSERT INTO memory VALUES (?,?,?,?,?)",
            (time.time(), user, cmd, winner["agent"], winner["final"])
        )
        self.db.commit()

        self.user_memory.setdefault(user, []).append(cmd)

    def route(self, user, cmd):
        if cmd == "/memory":
            return self.user_memory.get(user, [])
        return self.swarm(user, cmd)

    def loop(self):
        print("\n🚀 SWARM READY\nformat: user:message\n")

        try:
            while True:
                raw = input(">>> ").strip()
                if raw == "exit":
                    break

                if ":" not in raw:
                    print("format: user:message")
                    continue

                user, cmd = raw.split(":",1)
                res = self.route(user, cmd)

                print("\n📡 RESULT:\n")
                print(json.dumps(res, indent=2, ensure_ascii=False))

        except KeyboardInterrupt:
            print("\n🛑 EXIT CLEAN")

# BOOT
os = SwarmV14()
os.register("telegram", TelegramAgent())
os.register("smart", SmartAgent())
os.register("analytics", AnalyticsAgent())
os.loop()

PY

echo "🧠 Running..."
python swarm_v14.py

