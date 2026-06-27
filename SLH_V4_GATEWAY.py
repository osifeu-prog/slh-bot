import time
from SLH_V4_KERNEL import SLHV4Kernel
from SLH_V4_AGENTS import TelegramAgent, AnalyticsAgent, RevenueAgent


class SLHGateway:

    def __init__(self):
        self.kernel = SLHV4Kernel()

        # ONLY gateway registers agents
        self.kernel.register("telegram", TelegramAgent())
        self.kernel.register("analytics", AnalyticsAgent())
        self.kernel.register("revenue", RevenueAgent())

        print("🌐 Gateway ready")

    def handle(self, source, cmd, payload=None):
        event = {
            "source": source,
            "cmd": cmd,
            "payload": payload or {},
            "value": (payload or {}).get("value", 0.0)
        }

        return self.kernel.route(event)
