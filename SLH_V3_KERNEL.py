import time
from queue import Queue
import threading


class SLHV3Kernel:

    def __init__(self):
        self.modules = {}
        self.events = Queue()
        self.revenue = 0.0
        print("🧠 SLH V3 BOOTED")

    # ---------------- REGISTER ----------------
    def register(self, name, module):
        self.modules[name] = module
        print(f"✅ module registered: {name}")

    # ---------------- EMIT ----------------
    def emit(self, event):
        event["timestamp"] = time.time()
        self.events.put(event)

    # ---------------- ROUTE ----------------
    def route(self, event):
        cmd = event.get("cmd", "")

        if cmd == "status":
            return {
                "modules": list(self.modules.keys()),
                "revenue": self.revenue
            }

        module_name = cmd.split(":")[0]
        module = self.modules.get(module_name)

        if module:
            result = module.handle(event)

            self.revenue += event.get("value", 0.0)
            return result

        return "❌ no module found"

    # ---------------- LOOP ----------------
    def loop(self):
        while True:
            if not self.events.empty():
                event = self.events.get()
                result = self.route(event)
                print("➡️ RESULT:", result)
            time.sleep(0.1)

    # ---------------- START ----------------
    def start(self):
        t = threading.Thread(target=self.loop, daemon=True)
        t.start()

        while True:
            time.sleep(1)


class TelegramModule:

    def handle(self, event):
        return f"telegram handled: {event['cmd']}"


if __name__ == "__main__":
    kernel = SLHV3Kernel()
    kernel.register("telegram", TelegramModule())

    kernel.start()
