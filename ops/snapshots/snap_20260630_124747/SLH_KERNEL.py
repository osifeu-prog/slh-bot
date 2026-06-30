import time
import json
import threading
from queue import Queue


class SLHKernel:
    def __init__(self):
        self.modules = {}
        self.events = Queue()
        self.running = True
        self.config = self.load_config()
        print("🧠 SLH KERNEL BOOTED")

    # ---------------- CONFIG ----------------
    def load_config(self):
        try:
            with open("config.json") as f:
                return json.load(f)
        except Exception:
            return {}

    # ---------------- MODULE SYSTEM ----------------
    def register_module(self, name, module):
        self.modules[name] = module
        print(f"✅ module registered: {name}")

    def get_module(self, name):
        return self.modules.get(name)

    # ---------------- STATUS ----------------
    def status(self):
        return {
            "running": self.running,
            "modules": list(self.modules.keys()),
            "queue_size": self.events.qsize()
        }

    # ---------------- EVENT BUS ----------------
    def emit(self, event):
        if not isinstance(event, dict):
            return "❌ invalid event"

        self.events.put({
            "cmd": event.get("cmd"),
            "payload": event.get("payload", {}),
            "source": event.get("source", "system"),
            "ts": time.time()
        })

    # ---------------- ROUTER ----------------
    def route(self, command, payload=None):
        print(f"[ROUTE] {command} | {payload}")

        if command == "status":
            return self.status()

        if command == "modules":
            return list(self.modules.keys())

        module_name = command.split(":")[0]
        module = self.get_module(module_name)

        if module:
            return module.handle(command, payload)

        return "❌ Unknown command"

    # ---------------- LOOP ----------------
    def loop(self):
        while self.running:
            if not self.events.empty():
                event = self.events.get()
                self.route(event.get("cmd"), event.get("payload"))
            time.sleep(0.1)

    # ---------------- START ----------------
    def start(self):
        print("🚀 KERNEL STARTING")

        t = threading.Thread(target=self.loop, daemon=True)
        t.start()

        while self.running:
            time.sleep(1)


class BaseModule:
    def handle(self, command, payload):
        raise NotImplementedError


class TelegramModule(BaseModule):
    def handle(self, command, payload):
        if command == "telegram:ping":
            return "pong"
        return f"telegram received: {command}"


if __name__ == "__main__":
    kernel = SLHKernel()

    kernel.register_module("telegram", TelegramModule())

    print("📦 modules:", kernel.status())

    kernel.start()
