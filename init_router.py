from core.bootstrap_commands import init as init_commands
from core.command_router import HANDLERS

def bootstrap():
    print("🚀 Bootstrapping command system...")
    init_commands()
    print(f"✅ Commands loaded: {len(HANDLERS)}")
