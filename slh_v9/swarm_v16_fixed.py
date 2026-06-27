import os, time, json, sqlite3, asyncio, threading
from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters

# ============ CONFIG ============
def load_token():
    paths = [
        "config.json",
        os.path.expanduser("~/slh_clean/config.json"),
        os.path.expanduser("~/config.json")
    ]
    for p in paths:
        if os.path.exists(p):
            try:
                with open(p) as f:
                    return json.load(f)["BOT_TOKEN"]
            except:
                pass
    return os.getenv("TELEGRAM_BOT_TOKEN")

TOKEN = load_token()
if not TOKEN:
    print("⚠️ No BOT_TOKEN found. Telegram disabled.")
    TELEGRAM_ENABLED = False
else:
    TELEGRAM_ENABLED = True

# ============ AGENTS ============
class TelegramAgent:
    def handle(self, e):
        cmd = e["cmd"]
        if "ping" in cmd:
            return {"output": "pong", "score": 0.95}
        return {"output": "tg:"+cmd, "score": 0.6}

class SmartAgent:
    def handle(self, e):
        return {"output": "smart:"+e["cmd"], "score": 0.85}

class AnalyticsAgent:
    def handle(self, e):
        return {"output": "analytics:"+e["cmd"], "score": 0.55}

# ============ SWARM ============
class SwarmV16Fixed:
    def __init__(self):
        self.agents = {}
        self.reputation = {}
        self.memory = {}
        self.running = True
        self.db = sqlite3.connect("swarm_v16_fixed.db", check_same_thread=False)
        self._db()
        self._roadmap = [
            "telegram gateway ✅",
            "memory system ✅",
            "plugin engine",
            "reputation learning ✅",
            "revenue tracker",
            "telegram bot ✅ (v16.1)"
        ]
        print("🧠 SWARM V16.1 FIXED ONLINE")

    def _db(self):
        cur = self.db.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS memory (
            ts REAL, user TEXT, cmd TEXT, winner TEXT, score REAL
        )
        """)
        self.db.commit()

    def register(self, name, agent):
        self.agents[name] = agent
        self.reputation[name] = 1.0
        print("✅", name)

    def score(self, name, r):
        return r["score"] * self.reputation[name]

    def run_agent(self, name, agent, event):
        try:
            r = agent.handle(event)
            r["agent"] = name
            r["final"] = self.score(name, r)
            return r
        except Exception as e:
            return {"agent": name, "output": str(e), "score": 0, "final": 0}

    def swarm(self, user, cmd):
        event = {"user": user, "cmd": cmd}
        results = [self.run_agent(n, a, event) for n, a in self.agents.items()]
        winner = max(results, key=lambda x: x["final"])
        self._learn(winner)
        self._save(user, cmd, winner)
        return {"winner": winner, "all": results, "roadmap": self._roadmap}

    def _learn(self, w):
        n = w["agent"]
        self.reputation[n] = self.reputation[n]*0.93 + w["final"]*0.07

    def _save(self, user, cmd, winner):
        cur = self.db.cursor()
        cur.execute("INSERT INTO memory VALUES (?,?,?,?,?)",
                    (time.time(), user, cmd, winner["agent"], winner["final"]))
        self.db.commit()
        self.memory.setdefault(user, []).append(cmd)

    def route(self, user, cmd):
        if cmd == "/roadmap":
            return self._roadmap
        if cmd == "memory":
            return self.memory.get(user, [])
        return self.swarm(user, cmd)

# ============ TELEGRAM BOT (main thread) ============
async def run_bot(swarm):
    if not TELEGRAM_ENABLED:
        print("⚠️ Bot disabled")
        return

    app = Application.builder().token(TOKEN).build()

    async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = str(update.effective_user.id)
        text = update.message.text
        res = swarm.route(user, text)
        if isinstance(res, dict) and "winner" in res:
            w = res["winner"]
            reply = f"🏆 {w['agent']} → {w['output']} (score: {w['final']:.3f})"
        else:
            reply = str(res)
        await update.message.reply_text(reply)

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    print("🤖 Telegram bot running (polling)")
    # stop_signals=[] avoids signal handler issues
    await app.run_polling(stop_signals=[])

# ============ CLI (in daemon thread) ============
def cli(swarm):
    print("\n🚀 CLI READY (type 'exit' to quit, Ctrl+C to force stop)\n")
    while swarm.running:
        try:
            raw = input(">>> ").strip()
            if raw.lower() == "exit":
                swarm.running = False
                break
            if ":" not in raw:
                print("ℹ️  Format: user:message")
                continue
            user, cmd = raw.split(":", 1)
            res = swarm.route(user, cmd)
            print(json.dumps(res, indent=2, ensure_ascii=False))
        except (KeyboardInterrupt, EOFError):
            print("\n🛑 Stopping...")
            swarm.running = False
            break
    print("👋 CLI stopped.")

# ============ MAIN ============
def main():
    swarm = SwarmV16Fixed()
    swarm.register("telegram", TelegramAgent())
    swarm.register("smart", SmartAgent())
    swarm.register("analytics", AnalyticsAgent())

    # Start CLI in background thread
    t = threading.Thread(target=cli, args=(swarm,), daemon=True)
    t.start()

    # Run Telegram bot in main thread (asyncio)
    if TELEGRAM_ENABLED:
        asyncio.run(run_bot(swarm))
    else:
        # If no bot, keep main thread alive until CLI exits
        while swarm.running:
            time.sleep(0.5)

if __name__ == "__main__":
    main()
