import json

cfg = json.load(open("config.json"))

token = cfg.get("BOT_TOKEN", "")

if ":" not in token:
    print("❌ INVALID TOKEN in config.json")
    print("👉 Fix it or set real Telegram token")
    exit(1)

print("✅ Token format OK")
