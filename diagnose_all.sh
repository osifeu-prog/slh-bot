#!/data/data/com.termux/files/usr/bin/bash
echo "══════════════════════════════════════════════"
echo "  SLH OS – FULL CONFIG & INFRA DIAGNOSTIC"
echo "══════════════════════════════════════════════"
echo ""

# 1. Config.json check
echo "[1] Config.json"
python3 << 'PYEOF'
import json, os
path = "config.json"
if not os.path.exists(path):
    print("  ❌ config.json MISSING")
    exit(1)
with open(path) as f:
    cfg = json.load(f)
token = cfg.get("BOT_TOKEN", "")
print(f"  ✅ config.json exists")
print(f"  Token length: {len(token)}")
print(f"  Has colon: {':' in token}")
print(f"  First part digits: {token.split(':')[0].isdigit() if ':' in token else 'N/A'}")
PYEOF
echo ""

# 2. Daemon BOT_TOKEN export check
echo "[2] Daemon token export"
grep "export BOT_TOKEN" slh_daemon.sh || echo "  ❌ No BOT_TOKEN export in daemon"
echo ""

# 3. Telegram token validity
echo "[3] Telegram Token"
python3 << 'PYEOF'
import json, urllib.request
with open("config.json") as f:
    token = json.load(f)["BOT_TOKEN"]
try:
    resp = urllib.request.urlopen(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
    data = json.loads(resp.read())
    if data["ok"]:
        print(f"  ✅ Token valid – @{data['result']['username']}")
    else:
        print(f"  ❌ Token invalid: {data.get('description', 'unknown')}")
except Exception as e:
    print(f"  ❌ Cannot verify token: {e}")
PYEOF
echo ""

# 4. Railway connection status
echo "[4] Railway API"
TOKEN=$(cat ~/.railway_token 2>/dev/null)
if [ -z "$TOKEN" ]; then
    echo "  ❌ No Railway token in ~/.railway_token"
else
    echo "  Token length: ${#TOKEN}"
    PROJ=$(curl -s -H "Authorization: Bearer $TOKEN" \
        "https://backboard.railway.app/graphql/v2" \
        -d '{"query":"{ projects { edges { node { name } } } }"}' | jq -r '.data.projects.edges[0].node.name' 2>/dev/null)
    if [ -n "$PROJ" ] && [ "$PROJ" != "null" ]; then
        echo "  ✅ Railway connection OK – project: $PROJ"
    else
        echo "  ❌ Railway connection FAILED (token may be expired)"
    fi
fi
echo ""

# 5. Git status
echo "[5] Git"
echo "  Branch: $(git branch --show-current)"
echo "  Last commit: $(git log -1 --oneline)"
git status --short | head -5
echo ""

# 6. Processes
echo "[6] Processes"
pgrep -af "python3.*bot.py" || echo "  ❌ Bot not running"
pgrep -af "web/api/app.py" || echo "  ❌ API not running"
pgrep -af "http.server 8000" || echo "  ❌ Dashboard not running"
echo ""

# 7. API health
echo "[7] API Health"
curl -s http://localhost:5000/api/health 2>/dev/null || echo "  ❌ API not responding"
echo ""

echo "══════════════════════════════════════════════"
echo "  DIAGNOSTIC COMPLETE"
echo "══════════════════════════════════════════════"
