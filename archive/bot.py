import time
import json
import os
import threading
import subprocess
from queue import Queue
import uuid

from control_layer import ControlLayer

# =========================
# CONFIG
# =========================
CONFIG_PATH = "config.json"

def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)

# =========================
# JOURNAL
# =========================
class Journal:
    def log(self, msg):
        print(f"[JOURNAL] {time.strftime('%H:%M:%S')} | {msg}")

J = Journal()

# =========================
# EXEC
# =========================
class Exec:
    def run(self, cmd):
        J.log(f"RUN: {cmd}")
        return subprocess.getoutput(cmd)

# =========================
# CORE SYSTEM
# =========================
class SLHCore:
    def __init__(self):
        self.exec = Exec()
        self.events = Queue()

        self.cfg = load_config()
        self.admin_id = self.cfg.get("SUPER_ADMIN")

        self.control = ControlLayer(self)

        self.running = True

        J.log("CONTROL LAYER ATTACHED")

    # reload config
    def reload(self):
        self.cfg = load_config()
        J.log("CONFIG RELOADED")

    # emit event
    def emit(self, event):
        self.events.put(event)

    # ---------------- LOOP ----------------
    def loop(self):
        while self.running:

            if not self.events.empty():
                e = self.events.get()

                # format: ("user_id", "command", args)
                user_id, cmd, args = e

                J.log(f"CMD: {cmd} | USER: {user_id}")

                result = self.control.execute(user_id, cmd, args)

                print(result)

            time.sleep(0.2)

    # ---------------- SIMULATION ----------------
    def simulate(self):
        while True:
            time.sleep(3)
            self.emit((self.admin_id, "status", None))

    # ---------------- START ----------------
    def start(self):
        J.log("SYSTEM STARTED WITH CONTROL LAYER")

        threading.Thread(target=self.loop, daemon=True).start()
        threading.Thread(target=self.simulate, daemon=True).start()

        while True:
            time.sleep(1)

if __name__ == "__main__":
    SLHCore().start()
