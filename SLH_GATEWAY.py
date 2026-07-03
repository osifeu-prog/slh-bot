import time
from SLH_KERNEL import SLHKernel

KERNEL = SLHKernel()

class SLHGateway:
    def __init__(self):
        self.kernel = KERNEL
        print("🌐 Gateway ready (stable)")

    def send(self, source, cmd, payload=None):
        event = {
            "source": source,
            "cmd": cmd,
            "payload": payload or {},
            "timestamp": time.time()
        }
        return self.kernel.route(event)
