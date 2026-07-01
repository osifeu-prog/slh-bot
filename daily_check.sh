#!/data/data/com.termux/files/usr/bin/bash
echo "============================================="
echo "  SLH OS – DAILY HEALTH CHECK"
echo "============================================="
echo "Date: $(date)"
echo ""

# 1. Processes
echo "[1] Processes"
pgrep -f "python3.*bot_stable.py" > /dev/null 2>&1 && echo "  ✅ Bot running" || echo "  ❌ Bot not running"
pgrep -f "web/api/app.py" > /dev/null 2>&1 && echo "  ✅ API running" || echo "  ❌ API not running"
pgrep -f "http.server 8000" > /dev/null 2>&1 && echo "  ✅ Dashboard running" || echo "  ❌ Dashboard not running"
echo ""

# 2. API Endpoints
echo "[2] API Endpoints"
curl -s http://localhost:5000/api/health | grep -q '"ok"' && echo "  ✅ /api/health OK" || echo "  ❌ /api/health FAIL"
curl -s http://localhost:5000/api/stats | grep -q '"version"' && echo "  ✅ /api/stats OK" || echo "  ❌ /api/stats FAIL"
curl -s http://localhost:5000/api/logs?n=1 | grep -q '^\[' && echo "  ✅ /api/logs OK" || echo "  ❌ /api/logs FAIL"
echo ""

# 3. Dashboard
echo "[3] Dashboard"
DASH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/)
if [ "$DASH" = "200" ] || [ "$DASH" = "304" ]; then echo "  ✅ Dashboard HTTP $DASH"; else echo "  ❌ Dashboard HTTP $DASH"; fi
echo ""

# 4. Database
echo "[4] Database"
python3 -c "import json; db=json.load(open('db.json')); print(f'  ✅ DB OK – users:{len(db.get(\"users\",{}))}, tasks:{len(db.get(\"tasks\",[]))}, votes:{len(db.get(\"votes\",{}))}, agents:{len(db.get(\"agents\",{}))}')" 2>&1 || echo "  ❌ DB error"
echo ""

# 5. Kernel
echo "[5] Kernel"
python3 -c "from core.event_bus import EventBus; print('  ✅ EventBus OK')" 2>&1 || echo "  ❌ Kernel import failed"
echo ""

# 6. Agent OS
echo "[6] Agent OS"
python3 -c "
import sys; sys.path.insert(0,'.')
from bot import agents_dict
print(f'  ✅ Agent OS active – {len(agents_dict)} agents')
" 2>&1 || echo "  ⚠️ Agent OS not loaded (create one via /agent_create)"
echo ""

# 7. Audit
echo "[7] Audit"
python3 -c "from audit_logger import get_audit; print(f'  ✅ Audit entries: {len(get_audit(1000))}')" 2>&1 || echo "  ❌ Audit import failed"
echo ""

# 8. Master Agent
echo "[8] Master Agent"
python3 -c "from master_agent import MasterAgent; print('  ✅ Master Agent OK')" 2>&1 || echo "  ❌ Master Agent import failed"
echo ""

# 9. Inspector Agent
echo "[9] Inspector Agent"
python3 -c "from inspector import InspectorAgent; print('  ✅ Inspector Agent OK')" 2>&1 || echo "  ❌ Inspector Agent import failed"
echo ""

# 10. Telegram Token
echo "[10] Telegram Token"
python3 -c "
import json, urllib.request
with open('config.json') as f: token = json.load(f)['BOT_TOKEN']
resp = urllib.request.urlopen(f'https://api.telegram.org/bot{token}/getMe')
data = json.loads(resp.read())
print(f'  ✅ Token OK – @{data[\"result\"][\"username\"]}' if data['ok'] else '  ❌ Token invalid')
" 2>&1 || echo "  ❌ Token check failed"
echo ""

# 11. Git
echo "[11] Git"
git status > /dev/null 2>&1 && echo "  ✅ Git OK" || echo "  ❌ Git issue"
echo ""

# 12. Railway Token
echo "[12] Railway Token"
if [ -f ~/.railway_token ]; then
    TOKEN=$(cat ~/.railway_token)
    PROJ=$(curl -s -H "Authorization: Bearer $TOKEN" "https://backboard.railway.app/graphql/v2" -d '{"query":"{ projects { edges { node { name } } } }"}' | jq -r '.data.projects.edges[0].node.name' 2>/dev/null)
    if [ -n "$PROJ" ] && [ "$PROJ" != "null" ]; then echo "  ✅ Railway API OK ($PROJ)"; else echo "  ⚠️ Railway token expired"; fi
else
    echo "  ⚠️ No Railway token"
fi
echo ""

echo "============================================="
echo "  DAILY CHECK COMPLETE"
echo "============================================="
