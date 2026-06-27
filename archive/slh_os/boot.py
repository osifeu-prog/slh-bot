import json
import time
import sqlite3
import telebot
import threading
from queue import Queue

class SLHOS:

    def __init__(self):

        self.config = self.safe_load_config()
        self.token = self.config.get("BOT_TOKEN", "")

        self.db = sqlite3.connect("memory.db", check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS memory (k TEXT, v TEXT)")

        self.bus = Queue()
        self.agents = {}

        self.bot = None
        if self.token and ":" in self.token:
            self.bot = telebot.TeleBot(self.token)
        else:
            print("⚠️ SAFE MODE ACTIVE")

    # ---------------- SAFE CONFIG ----------------
    def safe_load_config(self):
        try:
            return json.load(open("config.json"))
        except:
            return {}

    # ---------------- MEMORY ----------------
    def save(self, k, v):
        self.db.execute("INSERT INTO memory VALUES (?,?)", (k,v))
        self.db.commit()

    def load(self, k):
        cur = self.db.execute("SELECT v FROM memory WHERE k=?", (k,))
        return cur.fetchall()

    # ---------------- CONTROL ENGINE ----------------
    def execute(self, command):

        if command["type"] == "memory_save":
            self.save(command["key"], command["value"])
            return "saved"

        if command["type"] == "memory_load":
            return self.load(command["key"])

        if command["type"] == "agent_create":
            name = command.get("name", "agent")
            self.agents[name] = {"status": "active", "tasks": []}
            return f"agent {name} created"

        return "unknown command"

    # ---------------- EVENT LOOP ----------------
    def event_loop(self):
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
            self.bot.reply_to(m, "🚀 SLH OS CONTROL API ACTIVE")

        @self.bot.message_handler(commands=['save'])
        def save(m):
            self.bus.put({
                "type": "memory_save",
                "key": "last_user",
                "value": str(m.from_user.id)
            })
            self.bot.reply_to(m, "queued")

        @self.bot.message_handler(commands=['load'])
        def load(m):
            self.bus.put({
                "type": "memory_load",
                "key": "last_user"
            })
            self.bot.reply_to(m, "queued")

        @self.bot.message_handler(commands=['agent'])
        def agent(m):
            self.bus.put({
                "type": "agent_create",
                "name": "agent_" + str(m.from_user.id)
            })
            self.bot.reply_to(m, "agent queued")

    # ---------------- RUN ----------------
    def run(self):

        threading.Thread(target=self.event_loop, daemon=True).start()

        if not self.bot:
            while True:
                time.sleep(10)

        self.register()
        print("🔥 SLH OS CONTROL API RUNNING")
        self.bot.infinity_polling()

if __name__ == "__main__":
    SLHOS().run()
