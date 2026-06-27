import json
import time
import sqlite3
import telebot
from queue import Queue

class SLHCoreV2:

    def __init__(self):
        self.config = self.safe_load()
        self.token = self.config.get("BOT_TOKEN", "")

        self.db = sqlite3.connect("memory.db", check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS memory (k TEXT, v TEXT)")

        self.bus = Queue()

        # agents רק registry (לא רצים עדיין)
        self.agents = {}

        self.bot = None
        if self.token and ":" in self.token:
            self.bot = telebot.TeleBot(self.token)

        print("🧠 SLH CORE V2 INITIALIZED")

    # ---------------- SAFE CONFIG ----------------
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

    # ---------------- CONTROL ----------------
    def execute(self, cmd):

        if cmd["type"] == "save":
            self.save(cmd["key"], cmd["value"])
            return "saved"

        if cmd["type"] == "load":
            return self.load(cmd["key"])

        if cmd["type"] == "agent_create":
            name = cmd["name"]
            self.agents[name] = {
                "status": "idle",
                "tasks": []
            }
            return f"agent {name} created (idle)"

        return "unknown"

    # ---------------- EVENT LOOP ----------------
    def loop(self):
        while True:
            if not self.bus.empty():
                cmd = self.bus.get()
                result = self.execute(cmd)
                print("[EXEC]", cmd, "=>", result)
            time.sleep(1)

    # ---------------- TELEGRAM ----------------
    def register(self):

        if not self.bot:
            return

        @self.bot.message_handler(commands=['start'])
        def start(m):
            self.bot.reply_to(m, "🚀 SLH OS V2 STABLE ONLINE")

        @self.bot.message_handler(commands=['save'])
        def save(m):
            self.bus.put({
                "type": "save",
                "key": "last_user",
                "value": str(m.from_user.id)
            })
            self.bot.reply_to(m, "queued")

        @self.bot.message_handler(commands=['load'])
        def load(m):
            self.bus.put({
                "type": "load",
                "key": "last_user"
            })
            self.bot.reply_to(m, "queued")

        @self.bot.message_handler(commands=['agent'])
        def agent(m):
            self.bus.put({
                "type": "agent_create",
                "name": f"agent_{m.from_user.id}"
            })
            self.bot.reply_to(m, "agent registered")

    # ---------------- RUN ----------------
    def run(self):
        import threading
        threading.Thread(target=self.loop, daemon=True).start()

        if not self.bot:
            print("⚠️ SAFE MODE")
            while True:
                time.sleep(10)

        self.register()
        print("🔥 SLH OS V2 RUNNING")
        self.bot.infinity_polling()

if __name__ == "__main__":
    SLHCoreV2().run()
