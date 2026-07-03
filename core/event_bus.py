import threading, time, json
from core.event_store import EventStore

class EventBus:
    def __init__(self, workers=3):
        self.store = EventStore()
        self.handlers = {}
        self.running = False
        self.workers = workers

    def register(self, event, handler):
        self.handlers.setdefault(event, []).append(handler)

    def emit(self, event, payload):
        self.store.add(event, payload)

    def _process(self, event_id, event, payload):
        handlers = self.handlers.get(event, [])
        for h in handlers:
            try:
                h(payload)
            except Exception as e:
                print("[EVENT ERROR]", event, e)
        self.store.mark_done(event_id)

    def worker_loop(self, wid):
        print(f"[WORKER {wid}] started")
        while self.running:
            batch = self.store.fetch_batch(limit=1)
            if not batch:
                time.sleep(0.3)
                continue
            for event_id, event, payload in batch:
                try:
                    self._process(event_id, event, json.loads(payload))
                except Exception as e:
                    print("[WORKER ERROR]", wid, e)

    def start(self):
        if self.running:
            return
        self.running = True
        for i in range(self.workers):
            t = threading.Thread(target=self.worker_loop, args=(i,), daemon=True)
            t.start()
