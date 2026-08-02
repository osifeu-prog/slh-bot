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

def get_balance(uid):
    """Return user balance in credits"""
    import json
    try:
        with open('state/db.json') as f:
            db = json.load(f)
        return db.get('users', {}).get(str(uid), {}).get('wallet', {}).get('credits', 0)
    except:
        return 0

def get_supply():
    """Return total credits in circulation"""
    import json
    try:
        with open('state/db.json') as f:
            db = json.load(f)
        return sum(u.get('wallet', {}).get('credits', 0) for u in db.get('users', {}).values())
    except:
        return 0
