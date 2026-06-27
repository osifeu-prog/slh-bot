
import os
import time
import json
import sqlite3
import signal
from threading import Thread
from concurrent.futures import ThreadPoolExecutor

# =========================
# AGENTS
# =========================

class TelegramAgent:
    def handle(self, e):
        cmd = e["cmd"]
        if "ping" in cmd:
            return {"output":"pong", "score":0.95, "value":0.01}
        return {"output":"tg:"+cmd, "score":0.6, "value":0}

class SmartAgent:
    def handle(self, e):
        cmd = e["cmd"]
        score = 0.9 if "telegram" in cmd else 0.55
        return {"output":"smart:"+cmd, "score":score, "value":0}

class AnalyticsAgent:
    def handle(self, e):
        return {"output":"analytics:"+e["cmd"], "score":0.58, "value":0}

# =========================
# SWARM CORE V15
# =========================

class SwarmV15:

    def __init__(self):
        self.agents = {}
        self.reputation = {}
        self.user_memory = {}
        self.running = True

        self.db = sqlite3.connect("swarm_v15.db", check_same_thread=False)
        self._db()

        self.pool = ThreadPoolExecutor(max_workers=4)

        print("🧠 SWARM V15 ONLINE (DAEMON READY)")

        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)

    def shutdown(self, *_):
        print("\n🛑 SHUTDOWN INITIATED...")
        self.running = False

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
        except Exception as e:
            return {"agent": name, "output": str(e), "score": 0, "final": 0}

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

    def _learn(self, w):
        n = w["agent"]
        self.reputation[n] = self.reputation[n]*0.9 + w["final"]*0.1

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
        print("\n🚀 CLI READY (type user:message)\n")

        try:
            while self.running:
                raw = input(">>> ").strip()

                if raw == "exit":
                    break

                if ":" not in raw:
                    continue

                user, cmd = raw.split(":",1)
                res = self.route(user, cmd)

                print(json.dumps(res, indent=2, ensure_ascii=False))

        except KeyboardInterrupt:
            self.shutdown()

# =========================
# TELEGRAM BOT
# =========================

def start_telegram(swarm):

    try:
        from telegram import Update
        from telegram.ext import Application, MessageHandler, CommandHandler, ContextTypes, filters
    except:
        print("❌ pip install python-telegram-bot")
        return

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("⚠️ Missing TELEGRAM_BOT_TOKEN")
        return

    app = Application.builder().token(token).build()

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🧠 Swarm V15 online")

    async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = str(update.effective_user.id)
        text = update.message.text

        result = swarm.route(user, text)

        if isinstance(result, list):
            reply = "📋 " + ", ".join(result)
        elif isinstance(result, dict):
            w = result.get("winner", {})
            reply = f"🏆 {w.get('agent')} → {w.get('output')} (score {w.get('final'):.2f})"
        else:
            reply = str(result)

        await update.message.reply_text(reply)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

    print("🤖 Telegram bot running (polling)")
    app.run_polling()

# =========================
# DAEMON MODE
# =========================

def daemon_mode():
    print("🧠 RUNNING IN DAEMON MODE (background ready)")
    while True:
        time.sleep(60)

# =========================
# MAIN
# =========================

def main():

    swarm = SwarmV15()

    swarm.register("telegram", TelegramAgent())
    swarm.register("smart", SmartAgent())
    swarm.register("analytics", AnalyticsAgent())

    mode = os.getenv("SWARM_MODE", "cli")

    if mode == "daemon":
        Thread(target=start_telegram, args=(swarm,), daemon=True).start()
        daemon_mode()
    else:
        Thread(target=start_telegram, args=(swarm,), daemon=True).start()
        swarm.loop()

if __name__ == "__main__":
    main()

