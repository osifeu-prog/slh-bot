from SLH_V8_KERNEL import SLHV8Kernel
from SLH_V8_AGENTS import TelegramAgent, SmartAgent, AnalyticsAgent
from SLH_V8_PLUGINS import LoggerPlugin, RevenuePlugin


class SLHGateway:

    def __init__(self):
        self.kernel = SLHV8Kernel()

        # agents
        self.kernel.register_agent("telegram", TelegramAgent())
        self.kernel.register_agent("smart", SmartAgent())
        self.kernel.register_agent("analytics", AnalyticsAgent())

        # plugins
        self.kernel.register_plugin("logger", LoggerPlugin())
        self.kernel.register_plugin("revenue", RevenuePlugin())

        print("🌐 V8 Gateway Ready")

    def handle(self, source, cmd, payload=None):
        return self.kernel.route({
            "source": source,
            "cmd": cmd,
            "payload": payload or {}
        })

    def emit(self, cmd):
        self.kernel.emit({
            "source": "external",
            "cmd": cmd
        })
