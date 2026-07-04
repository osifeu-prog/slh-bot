import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"

def get_token():
    if not CONFIG_PATH.exists():
        return None

    try:
        with open(CONFIG_PATH, "r") as f:
            data = json.load(f)
        return data.get("BOT_TOKEN")
    except Exception:
        return None
