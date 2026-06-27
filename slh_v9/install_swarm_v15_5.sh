#!/data/data/com.termux/files/usr/bin/bash

set -e

echo "🧠 SWARM V15.5 SELF-HEALING INSTALL"

BASE=~/slh_clean/slh_v9
mkdir -p $BASE
cd $BASE

# =========================
# CORE PYTHON
# =========================
cat > swarm_v15_5.py << 'PY'
import os
import time
import json
import sqlite3
import signal
import threading

# =========================
# LOCK (prevent double run)
# =========================
LOCK_FILE = "/data/data/com.termux/files/home/swarm.lock"

def acquire_lock():
    if os.path.exists(LOCK_FILE):
        print("⚠️ Swarm already running. Exiting.")
        exit(0)
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))

def release_lock():
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)

# =========================
# CONFIG LOADER (ENV + FILE)
# =========================
def load_token():
    token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not token:
        try:
            with open("config.json", "r") as f:
                token = json.load(f).get("BOT_TOKEN")
        except:
            token = None

    return token

# =========================
# AGENTS
# =========================
class TelegramAgent:
    def handle(self, e):
        cmd = e["cmd"]
        if "ping" in cmd:
            return {"output":"pong","score":0.95}
        return {"output":"tg:"+cmd,"score":0.6}

class SmartAgent:
    def handle(self, e):
        cmd = e["cmd"]
        return {"output":"smart:"+cmd,"score":0.7}

class AnalyticsAgent:
    def handle(self, e):
        return {"output":"analytics:"+e["cmd"],"score":0.5}

# =========================
# SWARM CORE
# =========================
class SwarmV15_5:

    def __init__(self):
        self.agents = {}
        self.reputation = {}
        self.running = True

        self.db = sqlite3.connect("swarm_v15_5.db", check_same_thread=False)
        self._db()

        print("🧠 SWARM V15.5 SELF-HEALING ONLINE")

        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)

    def shutdown(self, *_):
        print("\n🛑 Shutdown signal received")
        self.running = False
        release_lock()

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
        print("✅", name)

    def score(self, name, r):
        return r["score"] * self.reputation[name]

    def _run(self, name, agent, event):
        try:
            r = agent.handle(event)
            r["agent"] = name
            r["final"] = self.score(name, r)
            return r
        except:
            return {"agent":name,"output":"error","score":0,"final":0}

    def swarm(self, user, cmd):
        event = {"user":user,"cmd":cmd}

        results = [self._run(n,a,event) for n,a in self.agents.items()]
        winner = max(results, key=lambda x: x["final"])

        return {"user":user,"winner":winner,"all":results}

    def route(self, user, cmd):
        if cmd == "/memory":
            return []
        return self.swarm(user, cmd)

    def loop(self):
        print("\n🚀 CLI READY (SELF HEALING)\n")

        while self.running:
            try:
                raw = input(">>> ").strip()

                if raw == "exit":
                    break

                if ":" not in raw:
                    continue

                user, cmd = raw.split(":",1)
                res = self.route(user, cmd)

                print(json.dumps(res, indent=2))

            except Exception as e:
                print("⚠️ loop error:", e)
                time.sleep(1)

# =========================
# WATCHDOG (AUTO RESTART)
# =========================
def watchdog():
    while True:
        time.sleep(5)
        if not os.path.exists(LOCK_FILE):
            print("🔁 Swarm died → restarting...")
            os.system("python swarm_v15_5.py &")

# =========================
# BOOT
# =========================
def main():
    acquire_lock()

    swarm = SwarmV15_5()
    swarm.register("telegram", TelegramAgent())
    swarm.register("smart", SmartAgent())
    swarm.register("analytics", AnalyticsAgent())

    threading.Thread(target=watchdog, daemon=True).start()

    try:
        swarm.loop()
    finally:
        release_lock()

if __name__ == "__main__":
    main()
PY

# =========================
# RUN
# =========================
echo "🚀 Starting V15.5..."
python swarm_v15_5.py
