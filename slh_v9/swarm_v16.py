
import os
import time
import json
import sqlite3
import traceback
from threading import Thread

# optional telegram
try:
    from telegram import Update
    from telegram.ext import Application, MessageHandler, CommandHandler, ContextTypes, filters
    TELEGRAM = True
except:
    TELEGRAM = False


# =========================
# CONFIG LOADER (AUTO)
# =========================
def load_config():
    paths = [
        "config.json",
        os.path.expanduser("~/slh_clean/config.json"),
        os.path.expanduser("~/config.json")
    ]

    for p in paths:
        try:
            if os.path.exists(p):
                with open(p, "r") as f:
                    return json.load(f)
        except:
            pass
    return {}

CONFIG = load_config()
BOT_TOKEN = CONFIG.get("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")


# =========================
# AGENTS
# =========================
class TelegramAgent:
    def handle(self, e):
        cmd = e["cmd"]
        if "ping" in cmd:
            return {"output": "pong", "score": 0.95}
        return {"output": "tg:" + cmd, "score": 0.6}

class SmartAgent:
    def handle(self, e):
        cmd = e["cmd"]
        return {"output": "smart:" + cmd, "score": 0.85}

class AnalyticsAgent:
    def handle(self, e):
        return {"output": "analytics:" + e["cmd"], "score": 0.55}


# =========================
# SWARM CORE V16
# =========================
class SwarmV16:

    def __init__(self):
        self.agents = {}
        self.reputation = {}
        self.memory = {}
        self.running = True

        self.db = sqlite3.connect("swarm_v16.db", check_same_thread=False)
        self._db()

        self.log_file = open("swarm_v16.log", "a")

        print("🧠 SWARM V16 PRODUCTION ONLINE")

    # -------- DB --------
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

    # -------- REGISTER --------
    def register(self, name, agent):
        self.agents[name] = agent
        self.reputation[name] = 1.0
        print("✅", name)

    # -------- SCORE --------
    def score(self, name, r):
        return r["score"] * self.reputation[name]

    # -------- RUN --------
    def _run(self, name, agent, event):
        try:
            r = agent.handle(event)
            r["agent"] = name
            r["final"] = self.score(name, r)
            return r
        except Exception as e:
            return {"agent": name, "output": str(e), "score": 0, "final": 0}

    # -------- SWARM --------
    def swarm(self, user, cmd):

        event = {"user": user, "cmd": cmd}

        results = [self._run(n,a,event) for n,a in self.agents.items()]
        winner = max(results, key=lambda x: x["final"])

        self._save(user, cmd, winner)
        self._learn(winner)

        return {
            "user": user,
            "winner": winner,
            "all": results
        }

    # -------- LEARN --------
    def _learn(self, w):
        n = w["agent"]
        self.reputation[n] = self.reputation[n]*0.92 + w["final"]*0.08

    # -------- SAVE --------
    def _save(self, user, cmd, winner):
        cur = self.db.cursor()
        cur.execute(
            "INSERT INTO memory VALUES (?,?,?,?,?)",
            (time.time(), user, cmd, winner["agent"], winner["final"])
        )
        self.db.commit()

        self.memory.setdefault(user, []).append(cmd)

    # -------- ROUTER --------
    def route(self, user, cmd):

        if cmd == "/memory":
            return self.memory.get(user, [])

        return self.swarm(user, cmd)

    # -------- LOGGING --------
    def log(self, msg):
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {msg}\n"
        self.log_file.write(line)
        self.log_file.flush()

    # -------- CLI --------
    def cli(self):
        self.log("CLI STARTED")

        print("\n🚀 V16 CLI READY (type user:msg)\n")

        while self.running:
            try:
                raw = input(">>> ").strip()

                if raw == "exit":
                    break

                if ":" not in raw:
                    continue

                user, cmd = raw.split(":",1)

                res = self.route(user, cmd)
                print(res)

            except KeyboardInterrupt:
                self.log("CLI INTERRUPT")
                break
            except Exception as e:
                self.log("CLI ERROR " + str(e))

    # -------- SHUTDOWN --------
    def stop(self):
        self.running = False
        self.log("SHUTDOWN")

# =========================
# TELEGRAM BOT
# =========================
def start_telegram(swarm):

    if not TELEGRAM:
        print("⚠️ Telegram lib missing")
        return

    if not BOT_TOKEN:
        print("⚠️ No BOT TOKEN found (config.json or env)")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = str(update.effective_user.id)
        text = update.message.text

        result = swarm.route(user, text)

        if isinstance(result, dict):
            w = result.get("winner", {})
            reply = f"🏆 {w.get('agent')} → {w.get('output')} ({w.get('final'):.2f})"
        else:
            reply = str(result)

        await update.message.reply_text(reply)

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

    print("🤖 Telegram bot running")
    app.run_polling()

# =========================
# DAEMON ENGINE (SELF HEAL)
# =========================
def daemon():

    swarm = SwarmV16()

    swarm.register("telegram", TelegramAgent())
    swarm.register("smart", SmartAgent())
    swarm.register("analytics", AnalyticsAgent())

    # telegram thread
    Thread(target=start_telegram, args=(swarm,), daemon=True).start()

    while True:
        try:
            swarm.cli()
        except Exception as e:
            swarm.log("CRASH RECOVERED: " + str(e))
            time.sleep(2)
            continue

# =========================
# BOOT
# =========================
if __name__ == "__main__":
    daemon()

