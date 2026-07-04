import json
from pathlib import Path

REG_PATH = Path("state/commands_registry.json")

def load_commands_registry():
    if not REG_PATH.exists():
        return {}
    with open(REG_PATH, "r") as f:
        return json.load(f)


def is_valid_command(cmd: str) -> bool:
    registry = load_commands_registry()
    return cmd in registry


def get_command_module(cmd: str):
    registry = load_commands_registry()
    return registry.get(cmd, "unknown")
