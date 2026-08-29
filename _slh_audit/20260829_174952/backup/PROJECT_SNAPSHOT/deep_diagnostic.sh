#!/data/data/com.termux/files/usr/bin/bash
echo "══════════════════════════════════════════════"
echo "  SLH OS – DEEP DIAGNOSTIC"
echo "══════════════════════════════════════════════"
echo ""

# 1. ALL Python processes (not just bot)
echo "[1] ALL PYTHON PROCESSES"
ps aux | grep python3 | grep -v grep
echo ""

# 2. Who holds the token? (check via Telegram API)
echo "[2] TOKEN HOLDER CHECK"
python3 << 'PYEOF'
import json, urllib.request
with open("config.json") as f:
    token = json.load(f)["BOT_TOKEN"]
# Get bot info
try:
    resp = urllib.request.urlopen(f"https://api.telegram.org/bot{token}/getMe", timeout=5)
    data = json.loads(resp.read())
    if data["ok"]:
        print(f"  ✅ Token valid – @{data['result']['username']}")
    else:
        print(f"  ❌ Token error: {data.get('description')}")
except Exception as e:
    print(f"  ❌ Cannot reach Telegram: {e}")

# Try to get updates – if 409, someone else is holding the token
try:
    resp = urllib.request.urlopen(f"https://api.telegram.org/bot{token}/getUpdates", timeout=5)
    print("  ✅ No conflict – token is free")
except urllib.error.HTTPError as e:
    if e.code == 409:
        print("  ❌ 409 Conflict – SOMEONE ELSE IS USING THE TOKEN")
    else:
        print(f"  ❌ HTTP {e.code}: {e.reason}")
PYEOF
echo ""

# 3. Railway service status
echo "[3] RAILWAY SERVICE STATUS"
TOKEN=$(cat ~/.railway_token 2>/dev/null)
if [ -n "$TOKEN" ]; then
    curl -s -H "Authorization: Bearer $TOKEN" \
        "https://backboard.railway.app/graphql/v2" \
        -d '{"query":"{ service(id: \"13d97581-0199-4f6a-80d1-885c9304ffc5\") { id name deployments(first:1){edges{node{status}}} } }"}' | jq '.data.service | {name, status: .deployments.edges[0].node.status}'
fi
echo ""

# 4. Local bot log (last 5 lines)
echo "[4] LAST 5 BOT LOG LINES"
tail -5 bot.log 2>/dev/null || echo "  No bot.log"
echo ""

# 5. Check if bot.py can be imported
echo "[5] BOT.PY IMPORT TEST"
timeout 5 python3 -c "import sys; sys.path.insert(0,'.'); from bot import bot; print('  ✅ bot.py imports OK')" 2>&1 || echo "  ❌ bot.py import FAILED"
echo ""

echo "══════════════════════════════════════════════"
echo "  DEEP DIAGNOSTIC COMPLETE"
echo "══════════════════════════════════════════════"
