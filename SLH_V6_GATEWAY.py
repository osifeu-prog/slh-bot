from SLH_V6_KERNEL import SLHV6Kernel
from SLH_V6_AGENTS import TelegramAgent, AnalyticsAgent, SmartAgent


class SLHGateway:

    def __init__(self):
        self.kernel = SLHV6Kernel()

        self.kernel.register("telegram", TelegramAgent())
        self.kernel.register("analytics", AnalyticsAgent())
        self.kernel.register("smart", SmartAgent())

        print("🌐 V6 Gateway ready")

    def handle(self, source, cmd, payload=None):
        return self.kernel.route({
            "source": source,
            "cmd": cmd,
            "payload": payload or {}
        })
