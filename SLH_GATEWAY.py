import time
from SLH_V3_KERNEL import SLHV3Kernel, TelegramModule


# GLOBAL SINGLE INSTANCE (הדבר שחסר לך)
KERNEL = SLHV3Kernel()
KERNEL.register("telegram", TelegramModule())


class SLHGateway:

    def __init__(self):
        self.kernel = KERNEL
        print("🌐 Gateway ready (singleton kernel)")

    def handle_event(self, event):
        return self.kernel.route(event)

    def send(self, source, cmd, payload=None):
        event = {
            "source": source,
            "cmd": cmd,
            "payload": payload or {},
            "timestamp": time.time()
        }
        return self.handle_event(event)
