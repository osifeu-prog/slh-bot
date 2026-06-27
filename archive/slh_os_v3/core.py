import json
import time
import sqlite3
import telebot
import threading
import uuid
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
        self.db.execute("CREATE TABLE IF NOT EXISTS audit (ts, event)")

        self.bus = Queue()
        self.agents = {}

        self.bot = None

        if self.token and ":" in self.token:
            self.bot = telebot.TeleBot(self.token)

        print("🧠 SLH CORE STABLE BOOTED")

    # ---------------- CONFIG ----------------
    def safe_load(self):
        try:
            return json.load(open("config.json"))
        except:
            return {}

    # ---------------- AUDIT ----------------
    def log(self, event):
        self.db.execute(
            "INSERT INTO audit VALUES (?,?)",
            (time.time(), str(event))
        )
        self.db.commit()

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

                self.log(cmd)

                t = cmd.get("type")

                if t == "agent_create":
                    print(self.create_agent(cmd["name"]))

                if t == "agent_task":
                    print(self.dispatch(cmd["name"], cmd["task"]))

                if t == "save":
                    self.save(cmd["key"], cmd["value"])
                    print("[SAVED]")

                if t == "load":
                    print(self.load(cmd["key"]))

            time.sleep(0.3)

    # ---------------- TELEGRAM ----------------
    def telegram_loop(self):
        while True:
            try:
                print("🔥 Telegram polling started")

                self.bot.infinity_polling(
                    timeout=20,
                    long_polling_timeout=10,
                    skip_pending=True
                )

            except Exception as e:
                print("⚠️ Telegram restart:", e)
                time.sleep(5)

    # ---------------- REGISTER ----------------
    def register(self):

        if not self.bot:
            return

        @self.bot.message_handler(commands=['start'])
        def start(m):
            self.bot.reply_to(m, "🚀 SLH STABLE READY")

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
                "task": task_text,
                "id": str(uuid.uuid4())
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

        threading.Thread(target=self.loop, daemon=True).start()

        if not self.bot:
            print("⚠️ SAFE MODE")
            while True:
                time.sleep(10)

        self.register()

        threading.Thread(target=self.telegram_loop, daemon=True).start()

        print("🔥 SYSTEM RUNNING")

        while True:
            time.sleep(60)


if __name__ == "__main__":
    SLHCore().run()
