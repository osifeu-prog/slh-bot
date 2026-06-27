import json
import time
import sqlite3
import telebot
import threading
from queue import Queue, SimpleQueue

# =========================
# AGENT
# =========================
class Agent:
    def __init__(self, name):
        self.name = name
        self.tasks = SimpleQueue()
        self.alive = True

    def run(self):
        while self.alive:
            if not self.tasks.empty():
                task = self.tasks.get()
                print(f"[AGENT {self.name}] => {task}")
            time.sleep(0.3)


# =========================
# CORE
# =========================
class SLHCore:

    def __init__(self):
        self.config = self.safe_load()
        self.token = self.config.get("BOT_TOKEN", "")

        self.db = sqlite3.connect("memory.db", check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS memory (k TEXT, v TEXT)")

        self.bus = Queue()
        self.agents = {}

        self.bot = None
        self.bot_thread = None
        self.loop_thread = None

        if self.token and ":" in self.token:
            self.bot = telebot.TeleBot(self.token)

        print("🧠 SLH CORE v3.2 INIT")

    # ---------------- CONFIG ----------------
    def safe_load(self):
        try:
            return json.load(open("config.json"))
        except:
            return {}

    # ---------------- MEMORY ----------------
    def save(self, k, v):
        self.db.execute("INSERT INTO memory VALUES (?,?)", (k, v))
        self.db.commit()

    def load(self, k):
        cur = self.db.execute("SELECT v FROM memory WHERE k=?", (k,))
        return cur.fetchall()

    # ---------------- AGENTS ----------------
    def create_agent(self, name):
        if name in self.agents:
            return "exists"

        agent = Agent(name)
        self.agents[name] = agent

        threading.Thread(target=agent.run, daemon=True).start()
        return f"agent {name} started"

    def dispatch(self, name, task):
        if name not in self.agents:
            self.create_agent(name)

        self.agents[name].tasks.put(task)
        return "task queued"

    # ---------------- LOOP ----------------
    def loop(self):
        while True:
            if not self.bus.empty():
                cmd = self.bus.get()
                t = cmd.get("type")

                if t == "agent_create":
                    print("[EXEC]", self.create_agent(cmd["name"]))

                if t == "agent_task":
                    print("[EXEC]", self.dispatch(cmd["name"], cmd["task"]))

                if t == "save":
                    self.save(cmd["key"], cmd["value"])
                    print("[EXEC] saved")

                if t == "load":
                    print("[EXEC]", self.load(cmd["key"]))

            time.sleep(0.3)

    # =========================
    # TELEGRAM SAFE WATCHDOG
    # =========================
    def telegram_worker(self):
        while True:
            try:
                print("🔥 Telegram polling started")

                self.bot.infinity_polling(
                    timeout=20,
                    long_polling_timeout=10,
                    skip_pending=True,
                    none_stop=True
                )

            except Exception as e:
                print("⚠️ Telegram crashed -> restart in 5s:", e)
                time.sleep(5)

    # ---------------- REGISTER ----------------
    def register(self):
        if not self.bot:
            return

        @self.bot.message_handler(commands=['start'])
        def start(m):
            self.bot.reply_to(m, "🚀 SLH CORE v3.2 STABLE")

        @self.bot.message_handler(commands=['agent'])
        def agent(m):
            name = f"agent_{m.from_user.id}"
            self.bus.put({"type": "agent_create", "name": name})
            self.bot.reply_to(m, "queued")

        @self.bot.message_handler(commands=['task'])
        def task(m):
            parts = m.text.split(" ", 2)

            if len(parts) < 3:
                self.bot.reply_to(m, "use /task agent text")
                return

            _, name, task_text = parts

            self.bus.put({
                "type": "agent_task",
                "name": name,
                "task": task_text
            })

            self.bot.reply_to(m, "queued")

        @self.bot.message_handler(commands=['save'])
        def save(m):
            self.bus.put({
                "type": "save",
                "key": "last_user",
                "value": str(m.from_user.id)
            })

        @self.bot.message_handler(commands=['load'])
        def load(m):
            self.bus.put({
                "type": "load",
                "key": "last_user"
            })

    # ---------------- RUN ----------------
    def run(self):

        self.loop_thread = threading.Thread(target=self.loop, daemon=True)
        self.loop_thread.start()

        if not self.bot:
            print("⚠️ SAFE MODE")
            while True:
                time.sleep(10)

        self.register()

        self.bot_thread = threading.Thread(target=self.telegram_worker, daemon=True)
        self.bot_thread.start()

        print("🔥 SYSTEM RUNNING v3.2 STABLE")

        while True:
            time.sleep(60)


if __name__ == "__main__":
    SLHCore().run()
