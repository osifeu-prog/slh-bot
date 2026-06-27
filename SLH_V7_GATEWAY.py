from SLH_V7_KERNEL import SLHV7Kernel
from SLH_V7_AGENTS import TelegramAgent, SmartAgent, AnalyticsAgent


class SLHGateway:

    def __init__(self):
        self.kernel = SLHV7Kernel()

        self.kernel.register("telegram", TelegramAgent())
        self.kernel.register("smart", SmartAgent())
        self.kernel.register("analytics", AnalyticsAgent())

        print("🌐 V7 Gateway ready")

    def handle(self, source, cmd, payload=None):
        return self.kernel.route({
            "source": source,
            "cmd": cmd,
            "payload": payload or {}
        })
