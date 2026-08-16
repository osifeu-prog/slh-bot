import os
import json
import subprocess
from datetime import datetime

def ok(name, result):
    print("✅" if result else "❌", name)
    return result

def main():
    print("\n=== SLH DIAGNOSTIC ===")
    print(datetime.now().isoformat())

    results = []

    results.append(ok("Bot file exists", os.path.exists("bot_stable.py")))
    results.append(ok("Config exists", os.path.exists("config.json")))
    results.append(ok("DB exists", os.path.exists("state/db.json")))

    # config validation
    try:
        cfg = json.load(open("config.json"))
        results.append(ok("Token present", "BOT_TOKEN" in cfg or os.getenv("BOT_TOKEN")))
        results.append(ok("Admin set", cfg.get("SUPER_ADMIN") == 8789977826))
    except:
        results.append(False)

    # python sanity
    results.append(ok("Python OK", subprocess.call(["python3", "--version"]) == 0))

    # syntax check
    results.append(ok("Bot syntax OK", subprocess.call(["python3", "-m", "py_compile", "bot_stable.py"]) == 0))

    print("\n====================")
    print("PASS:", sum(results))
    print("FAIL:", len(results) - sum(results))

    if all(results):
        print("\n🎉 SYSTEM OK")
    else:
        print("\n⚠️ SYSTEM HAS ISSUES")

if __name__ == "__main__":
    main()
