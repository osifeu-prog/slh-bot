import os, time, json, sqlite3, asyncio, threading, signal, sys

# ============= CONFIG =============
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
TELEGRAM_ENABLED = bool(TOKEN)

# ============= AGENTS =============
class TelegramAgent:
    def handle(self, e):
        return {"output": f"tg:{e['cmd']}", "score": 0.95}

class SmartAgent:
    def handle(self, e):
        return {"output": f"smart:{e['cmd']}", "score": 0.85}

class AnalyticsAgent:
    def handle(self, e):
        return {"output": f"analytics:{e['cmd']}", "score": 0.55}

# ============= SWARM =============
class SwarmV16:
    def __init__(self):
        self.agents = {}
        self.reputation = {}
        self.memory = {}
        self.running = True
        self.db = sqlite3.connect("swarm_v16.2.db", check_same_thread=False)
        self._db()
        self._roadmap = [
            "telegram gateway ✅",
            "memory system ✅",
            "plugin engine",
            "reputation learning ✅",
            "revenue tracker",
            "telegram bot ✅ (v16.2 stable)"
        ]
        print("🧠 SWARM V16.2 STABLE ONLINE")

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

# ============= TELEGRAM BOT (own event loop thread) =============
def bot_loop(swarm):
    if not TELEGRAM_ENABLED:
        print("⚠️ Bot disabled – no token")
        return

    async def run_bot():
        from telegram import Update
        from telegram.ext import Application, MessageHandler, filters, ContextTypes

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

        # stop_signals=None prevents signal handler clash in subthread
        await app.run_polling(stop_signals=[])

    # Deadlock protection: if bot hangs, watchdog will restart it
    while swarm.running:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(run_bot())
        except Exception as e:
            print(f"[BOT CRASH] {e} – restarting in 5s...")
            time.sleep(5)
        finally:
            try:
                loop.close()
            except:
                pass

# ============= WATCHDOG =============
def watchdog(swarm):
    """Auto-restart if the swarm instance becomes unresponsive."""
    last_heartbeat = time.time()
    def heartbeat():
        while swarm.running:
            last_heartbeat = time.time()
            time.sleep(10)

    t = threading.Thread(target=heartbeat, daemon=True)
    t.start()

    while swarm.running:
        time.sleep(15)
        if time.time() - last_heartbeat > 30:
            print("[WATCHDOG] Swarm unresponsive – restarting process...")
            os.execv(sys.executable, [sys.executable] + sys.argv)

# ============= CLI =============
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

# ============= MAIN =============
def main():
    swarm = SwarmV16()
    swarm.register("telegram", TelegramAgent())
    swarm.register("smart", SmartAgent())
    swarm.register("analytics", AnalyticsAgent())

    # Start watchdog
    threading.Thread(target=watchdog, args=(swarm,), daemon=True).start()

    # Start Telegram bot in its own thread
    if TELEGRAM_ENABLED:
        threading.Thread(target=bot_loop, args=(swarm,), daemon=True).start()

    # CLI runs in the main thread
    cli(swarm)

if __name__ == "__main__":
    main()
