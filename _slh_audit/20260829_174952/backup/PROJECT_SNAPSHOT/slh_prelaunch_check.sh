#!/data/data/com.termux/files/usr/bin/bash

echo "================================="
echo "🚀 SLH PRE-LAUNCH SYSTEM CHECK"
echo "$(date)"
echo "================================="

echo ""
echo "=== LOCAL FILES ==="
ls -1 bot_stable.py config.json Dockerfile railway.json 2>/dev/null

echo ""
echo "=== TELEGRAM CONNECTION ==="
python3 - <<'PY'
import json,requests
try:
    t=json.load(open("config.json"))["BOT_TOKEN"]

    print("BOT:")
    print(requests.get(
        f"https://api.telegram.org/bot{t}/getMe"
    ).json())

    print("\nWEBHOOK:")
    print(requests.get(
        f"https://api.telegram.org/bot{t}/getWebhookInfo"
    ).json())

    print("\nUPDATES:")
    print(requests.get(
        f"https://api.telegram.org/bot{t}/getUpdates",
        params={"timeout":1}
    ).json())

except Exception as e:
    print("ERROR:",e)
PY


echo ""
echo "=== RAILWAY STATUS ==="
railway status

echo ""
echo "=== DEPLOYMENTS ==="
railway deployment list | head -20

echo ""
echo "=== VARIABLES CHECK ==="
railway variables | grep -E "BOT|START|STOP|RAILWAY"

echo ""
echo "=== HANDLERS ==="
grep -Rho "commands=\['[^']*'" . 2>/dev/null | sort -u

echo ""
echo "=== GROUP REFERENCES ==="
grep -RIn "chat_id\|group\|supergroup\|@ " *.py handlers plugins 2>/dev/null | head -100

echo ""
echo "=== POLLING ==="
grep -n "polling" bot_stable.py

echo ""
echo "=== RESTART COMMAND ==="
grep -n "restart" bot_stable.py

echo ""
echo "=== STATE ==="
find state -maxdepth 2 -type f 2>/dev/null | head -50

echo ""
echo "================================="
echo "✅ CHECK COMPLETE"
echo "================================="
