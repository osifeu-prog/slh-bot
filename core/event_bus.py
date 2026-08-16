import threading, time, json

class EventBus:
    _instance = None
    _pending = []

    def __init__(self, workers=2):
        self.handlers = {}
        self.running = False
        self.workers = workers
        EventBus._instance = self
        for event, handler in EventBus._pending:
            self.register(event, handler)
        EventBus._pending.clear()

    def register(self, event, handler):
        self.handlers.setdefault(event, []).append(handler)

    def emit(self, event, payload):
        for handler in self.handlers.get(event, []):
            try:
                handler(payload)
            except Exception as e:
                print("❌ Event handler error:", e)

    @classmethod
    def subscribe(cls, event, handler):
        if cls._instance:
            cls._instance.register(event, handler)
        else:
            cls._pending.append((event, handler))

    @classmethod
    def publish(cls, event, payload):
        if cls._instance:
            cls._instance.emit(event, payload)
        else:
            print("⚠️ EventBus instance not ready")

    def start(self):
        self.running = True
        print("✅ EventBus started")
