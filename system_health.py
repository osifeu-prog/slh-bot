import os, json, subprocess, sys
from datetime import datetime, timezone

def check_bot():
    # use .env token
    with open("state/.env") as f:
        for line in f:
            if line.startswith("export BOT_TOKEN="):
                token = line.split('"')[1]
                break
    import requests
    resp = requests.get(f"https://api.telegram.org/bot{token}/getMe")
    if resp.json().get("ok"):
        return f"✅ Bot @{resp.json()['result']['username']} online"
    return "❌ Bot offline"

def check_db():
    try:
        with open("state/db.json") as f:
            db = json.load(f)
        users = len(db.get("users", {}))
        agents = len(db.get("agents", {}))
        txs = len(db.get("transactions", []))
        return f"✅ DB: {users} users, {agents} agents, {txs} transactions"
    except:
        return "❌ DB error"

def check_files():
    required = ["bot_stable.py", "payment_handler.py", "ton_handler.py", "econ_handler.py"]
    missing = [f for f in required if not os.path.exists(f)]
    if missing:
        return f"❌ Missing: {missing}"
    return "✅ All core files present"

def check_python():
    try:
        for f in ["bot_stable.py", "payment_handler.py", "ton_handler.py", "econ_handler.py"]:
            subprocess.check_call([sys.executable, "-m", "py_compile", f], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return "✅ Python compiles clean"
    except:
        return "❌ Python compilation errors"

def check_git():
    try:
        out = subprocess.check_output(["git", "status", "--short"], text=True)
        if out.strip():
            return "⚠️ Git has uncommitted changes"
        return "✅ Git clean"
    except:
        return "❌ Git not available"

def main():
    print("╔══════════════════════════════╗")
    print("║   SLH OS System Health      ║")
    print("╚══════════════════════════════╝")
    print(check_bot())
    print(check_db())
    print(check_files())
    print(check_python())
    print(check_git())
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")

if __name__ == "__main__":
    main()
