from SLH_MODULES import BaseModule, TelegramModule

class SLHKernel:
    def __init__(self):
        self.modules = {
            "telegram": TelegramModule()
        }
        print("🧠 SLH KERNEL BOOTED (modular mode)")

    def register_module(self, name, module):
        self.modules[name] = module
        print(f"✅ module registered: {name}")

    def get_module(self, name):
        return self.modules.get(name)

    def status(self):
        return {
            "modules": list(self.modules.keys())
        }

    def route(self, event):
        if not isinstance(event, dict):
            return "❌ invalid event"

        print(f"[ROUTE] {event}")

        cmd = event.get("cmd")
        if not cmd:
            return "❌ missing cmd"

        if cmd == "status":
            return self.status()

        module_name = cmd.split(":")[0] if isinstance(cmd, str) else None

        module = self.get_module(module_name)

        if not module:
            return f"❌ unknown module: {module_name}"

        return module.handle(event)
