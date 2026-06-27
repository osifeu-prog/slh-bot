from SLH_V5_KERNEL import SLHV5Kernel
from SLH_V5_AGENTS import TelegramAgent, AnalyticsAgent, SmartAgent


class SLHGateway:

    def __init__(self):
        self.kernel = SLHV5Kernel()

        self.kernel.register("telegram", TelegramAgent())
        self.kernel.register("analytics", AnalyticsAgent())
        self.kernel.register("smart", SmartAgent())

        print("🌐 Gateway ready")

    def handle(self, source, cmd, payload=None):
        return self.kernel.route({
            "source": source,
            "cmd": cmd,
            "payload": payload or {}
        })
