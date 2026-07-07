from core.bootstrap_commands import init as init_commands
from core.command_router import HANDLERS

def bootstrap(bot):
    print("🚀 Bootstrapping command system...")
    init_commands(bot)
    print(f"✅ Commands loaded: {len(HANDLERS)}")
