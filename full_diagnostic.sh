#!/data/data/com.termux/files/usr/bin/bash
echo "══════════════════════════════════════════════"
echo "  SLH OS – FULL DIAGNOSTIC REPORT"
echo "══════════════════════════════════════════════"
echo ""

# 1. Processes
echo "[1] PROCESSES"
echo "Bot:"
pgrep -af "python3.*bot.py" || echo "  ❌ Not running"
echo "API:"
pgrep -af "web/api/app.py" || echo "  ❌ Not running"
echo "Dashboard:"
pgrep -af "http.server 8000" || echo "  ❌ Not running"
BOT_COUNT=$(pgrep -c "python3.*bot.py" 2>/dev/null)
echo "  Bot instances: $BOT_COUNT"
echo ""

# 2. Last logs
echo "[2] LAST LOGS"
tail -15 bot.log 2>/dev/null || echo "  No bot.log"
echo ""

# 3. Telegram connection
echo "[3] TELEGRAM"
python3 get_token.py | xargs -I {} curl -s "https://api.telegram.org/bot{}/getMe" | jq '{ok: .ok, username: .result.username}'
echo ""

# 4. Railway
echo "[4] RAILWAY"
TOKEN=$(cat ~/.railway_token 2>/dev/null)
if [ -z "$TOKEN" ]; then
    echo "  ❌ No Railway token"
else
    echo "  Token length: ${#TOKEN}"
    curl -s -H "Authorization: Bearer $TOKEN" \
        "https://backboard.railway.app/graphql/v2" \
        -d '{"query":"{ service(id: \"13d97581-0199-4f6a-80d1-885c9304ffc5\") { branch repo deployments(first:1){edges{node{status}}} } }"}' | jq '.data.service | {branch, repo, status: .deployments.edges[0].node.status}'
fi
echo ""

# 5. Local API
echo "[5] API"
curl -s http://localhost:5000/api/health | jq . 2>/dev/null || echo "  ❌ API not responding"
echo ""

# 6. Dashboard
echo "[6] DASHBOARD"
DASH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/)
echo "  HTTP Status: $DASH"
echo ""

# 7. Database
echo "[7] DATABASE"
python3 -c "import json; db=json.load(open('db.json')); print(f'  Users: {len(db.get(\"users\",{}))}, Tasks: {len(db.get(\"tasks\",[]))}, Agents: {len(db.get(\"agents\",{}))}')" 2>/dev/null || echo "  ❌ DB error"
echo ""

# 8. Agent OS
echo "[8] AGENT OS"
python3 -c "
import sys; sys.path.insert(0,'.')
from bot import agents_dict
print(f'  Agents: {len(agents_dict)}')
" 2>/dev/null || echo "  ⚠️ Agent OS not loaded"
echo ""

# 9. Kernel
echo "[9] KERNEL"
python3 -c "from core.event_bus import EventBus; print('  ✅ EventBus OK')" 2>/dev/null || echo "  ❌ Kernel import failed"
echo ""

# 10. Git
echo "[10] GIT"
echo "  Branch: $(git branch --show-current)"
echo "  Last commit: $(git log -1 --oneline)"
echo ""

echo "══════════════════════════════════════════════"
echo "  DIAGNOSTIC COMPLETE"
echo "══════════════════════════════════════════════"
