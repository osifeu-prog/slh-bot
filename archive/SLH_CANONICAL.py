"""
SLH OS — Canonical Architecture
= = = = = = = = = = = = = = = = = =

CORE: slh_os_v3/core.py
GATEWAY: SLH_CANONICAL.py (this file)
CONTRACT: Every module implements start/stop/status/health/reload
ENTRY: SLHCore().run()

= = = = = = = = = = = = = = = = = =
"""

import json
from abc import ABC, abstractmethod

# CONTRACT: Every module must implement this
class SLHModule(ABC):
    def __init__(self, name):
        self.name = name
        self.running = False
    
    @abstractmethod
    def start(self):
        """Start the module"""
        pass
    
    @abstractmethod
    def stop(self):
        """Stop the module"""
        pass
    
    @abstractmethod
    def status(self):
        """Return module status"""
        pass
    
    @abstractmethod
    def health(self):
        """Return module health"""
        pass
    
    @abstractmethod
    def reload(self):
        """Reload the module"""
        pass


# GATEWAY: Single entry point for all commands
class SLHGateway:
    def __init__(self):
        self.modules = {}
        self.config = self.load_config()
    
    def load_config(self):
        with open("config.json") as f:
            return json.load(f)
    
    def register_module(self, module: SLHModule):
        """Register a module that implements Contract"""
        if not isinstance(module, SLHModule):
            raise ValueError(f"{module.name} must implement SLHModule")
        self.modules[module.name] = module
        print(f"✅ Registered: {module.name}")
    
    def route(self, command, payload=None):
        """
        Route all commands through here
        /lppp status → route("status", {})
        /lppp agent create → route("agent", {"action": "create"})
        """
        print(f"[GATEWAY] {command} {payload or ''}")
        # To be implemented
        pass


# Example: Telegram as a Module (not the Core)
class TelegramModule(SLHModule):
    def __init__(self):
        super().__init__("telegram")
    
    def start(self):
        print("[TelegramModule] Starting polling...")
        self.running = True
    
    def stop(self):
        print("[TelegramModule] Stopping...")
        self.running = False
    
    def status(self):
        return {"name": "telegram", "running": self.running}
    
    def health(self):
        return "✅" if self.running else "❌"
    
    def reload(self):
        self.stop()
        self.start()


# Bootstrap
if __name__ == "__main__":
    print("🚀 SLH OS — Canonical Boot")
    
    gateway = SLHGateway()
    
    # Register modules
    telegram = TelegramModule()
    gateway.register_module(telegram)
    
    print("✅ Gateway ready")
    print("📊 Modules:", list(gateway.modules.keys()))

