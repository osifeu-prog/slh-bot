import json
import time
import sqlite3
import telebot
import threading
from queue import Queue
from control import ControlLayer

class SLHOS:

    def __init__(self):
        self.config = json.load(open("config.json"))
        self.token = self.config.get("BOT_TOKEN", "")

        self.db = sqlite3.connect("memory.db", check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS memory (k TEXT, v TEXT)")

        self.bus = Queue()
        self.agents = {}

        self.bot = None
        if self.token and ":" in self.token:
            self.bot = telebot.TeleBot(self.token)

        self.control = ControlLayer(self)

    # ---------------- MEMORY ----------------
    def save(self, k, v):
        self.db.execute("INSERT INTO memory VALUES (?,?)", (k,v))
        self.db.commit()

    def load(self, k):
        cur = self.db.execute("SELECT v FROM memory WHERE k=?", (k,))
        return cur.fetchall()

    # ---------------- EVENT LOOP ----------------
    def event_loop(self):
        while True:
            if not self.bus.empty():
                event = self.bus.get()
                result = self.control.route(event)
                print("[CONTROL]", event, "=>", result)
            time.sleep(1)

    # ---------------- TELEGRAM ----------------
    def register(self):

        @self.bot.message_handler(commands=['start'])
        def start(m):
            self.bot.reply_to(m, "🚀 SLH OS CONTROL LAYER ACTIVE")

        @self.bot.message_handler(commands=['save'])
        def save(m):
            self.bus.put({
                "type": "memory_save",
                "key": "last_user",
                "value": str(m.from_user.id)
            })
            self.bot.reply_to(m, "queued save")

        @self.bot.message_handler(commands=['load'])
        def load(m):
            self.bus.put({
                "type": "memory_load",
                "key": "last_user"
            })
            self.bot.reply_to(m, "queued load")

        @self.bot.message_handler(commands=['agent'])
        def agent(m):
            self.bus.put({
                "type": "agent_spawn",
                "name": "agent_" + str(m.from_user.id)
            })
            self.bot.reply_to(m, "agent queued")

    # ---------------- RUN ----------------
    def run(self):

        threading.Thread(target=self.event_loop, daemon=True).start()

        if not self.bot:
            print("⚠️ SAFE MODE")
            while True:
                time.sleep(10)

        self.register()
        print("🔥 SLH OS WITH CONTROL LAYER RUNNING")
        self.bot.infinity_polling()

if __name__ == "__main__":
    SLHOS().run()
