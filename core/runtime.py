import threading
import time
from collections import deque
from core.dispatcher import Dispatcher

class Runtime:
    def __init__(self, kernel):
        self.kernel = kernel
        self.dispatcher = Dispatcher(kernel)

        self.q = deque()
        self.running = False
        self.cb = None

    def set_callback(self, cb):
        self.cb = cb

    def emit(self, event):
        self.q.append(event)

    def worker(self):
        while self.running:
            if not self.q:
                time.sleep(0.01)
                continue

            event = self.q.popleft()

            result = self.dispatcher.dispatch(event)

            if self.cb:
                self.cb(result)

    def start(self):
        self.running = True
        threading.Thread(target=self.worker, daemon=True).start()

    def stop(self):
        self.running = False
