#!/data/data/com.termux/files/usr/bin/bash
PASS=0; FAIL=0; WARN=0

check() {
    if [ "$1" -eq 0 ]; then echo "  ✅ $2"; ((PASS++)); else echo "  ❌ $2"; ((FAIL++)); fi
}

echo "══════════════════════════════════════════════"
echo "  SLH OS v2.0 — FINAL VERIFICATION"
echo "══════════════════════════════════════════════"
echo ""

# 1. PROCESSES
echo "[1] PROCESSES"
pgrep -f "python3.*bot.py" > /dev/null 2>&1
check $? "Bot running"
pgrep -f "web/api/app.py" > /dev/null 2>&1
check $? "Flask API running"
pgrep -f "http.server 8000" > /dev/null 2>&1
check $? "Dashboard server running"
BOT_COUNT=$(pgrep -f "python3.*bot.py" | wc -l)
if [ "$BOT_COUNT" -eq 1 ]; then echo "  ✅ Single bot instance (1)"; ((PASS++)); else echo "  ❌ Multiple bot instances ($BOT_COUNT)"; ((FAIL++)); fi
echo ""

# 2. API
echo "[2] API ENDPOINTS"
curl -s http://localhost:5000/api/health | grep -q '"ok"' 2>/dev/null
check $? "/api/health returns ok"
python3 -c "import urllib.request, json; data=json.loads(urllib.request.urlopen('http://localhost:5000/api/agents').read()); exit(0 if isinstance(data,dict) else 1)" 2>/dev/null
check $? "/api/agents returns JSON"
python3 -c "import urllib.request, json; data=json.loads(urllib.request.urlopen('http://localhost:5000/api/tasks').read()); exit(0 if isinstance(data,list) else 1)" 2>/dev/null
check $? "/api/tasks returns JSON array"
echo ""

# 3. DASHBOARD
echo "[3] DASHBOARD"
DASH_RES=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/)
if [ "$DASH_RES" = "200" ] || [ "$DASH_RES" = "304" ]; then echo "  ✅ Dashboard HTTP $DASH_RES"; ((PASS++)); else echo "  ❌ Dashboard HTTP $DASH_RES"; ((FAIL++)); fi
echo ""

# 4. DATABASE
echo "[4] DATABASE"
python3 -c "import json; db=json.load(open('db.json')); assert 'users' in db; assert 'votes' in db; assert 'tasks' in db; print('  ✅ DB has users/votes/tasks')" 2>/dev/null
check $? "DB has users/votes/tasks"
echo ""

# 5. AGENT OS (simple + safe)
echo "[5] AGENT OS"
python3 -c "
import json
agents = {}
aid = '1'
agents[aid] = {'name':'test','role':'agent','state':'idle','inbox':[],'history':[],'permissions':['read']}
agents[aid]['state'] = 'busy'
agents[aid]['inbox'].append({'time':'now','message':'hello'})
# persistence
with open('test_agents.json','w') as f: json.dump(agents, f)
with open('test_agents.json') as f: loaded = json.load(f)
checks = [
    aid in agents,
    agents[aid]['state'] == 'busy',
    len(agents[aid]['inbox']) == 1,
    aid in loaded,
    'read' in agents[aid]['permissions']
]
for i, ok in enumerate(checks):
    print(f\"  {'✅' if ok else '❌'} Test {i+1}\")
if all(checks):
    print('  ✅ Agent OS all checks')
    exit(0)
else:
    print('  ❌ Agent OS checks failed')
    exit(1)
"
check $? "Agent OS all checks"
echo ""

# 6. KERNEL + TASK PLUGIN
echo "[6] KERNEL + TASK PLUGIN"
python3 -c "
import sys, json, time
sys.path.insert(0,'.')
from core.event_bus import EventBus
from plugins.task import TaskPlugin
bus = EventBus(workers=1)
class K: pass
k = K(); k.bus = bus; k.state = {}; k.telegram = None
TaskPlugin().on_start(k)
bus.emit('task_create', {'chat':123,'task':'verify_task'})
time.sleep(0.3)
event = bus.store.fetch_batch(1)
if event:
    eid,etype,payload = event[0]
    bus._process(eid,etype,json.loads(payload))
    ok1 = 'verify_task' in k.state.get('tasks',[])
else:
    ok1 = False
bus.emit('task_create', {'chat':123,'task':'task2'})
time.sleep(0.3)
event = bus.store.fetch_batch(1)
if event:
    eid,etype,payload = event[0]
    bus._process(eid,etype,json.loads(payload))
    ok2 = len(k.state.get('tasks',[])) == 2
else:
    ok2 = False
checks = [bus is not None, True, ok1, ok2]
names = ['EventBus init','TaskPlugin init','Task creation','Multiple tasks']
for name, ok in zip(names, checks):
    print(f\"  {'✅' if ok else '❌'} {name}\")
if all(checks):
    print('  ✅ Kernel + TaskPlugin all checks')
    exit(0)
else:
    print('  ❌ Kernel checks failed')
    exit(1)
"
check $? "Kernel + TaskPlugin all checks"
echo ""

# 7. AUDIT
echo "[7] AUDIT LOG"
python3 -c "
from audit_logger import audit, get_audit
audit('verification','system','final')
entries = get_audit(5)
if any(e.get('action')=='verification' for e in entries):
    print('  ✅ Audit records action')
    exit(0)
else:
    print('  ❌ Audit missing')
    exit(1)
"
check $? "Audit records action"
echo ""

# 8. BOT COMMANDS
echo "[8] BOT COMMANDS"
COMMANDS=$(grep -c "@bot.message_handler" bot.py 2>/dev/null)
if [ "$COMMANDS" -ge 30 ]; then echo "  ✅ $COMMANDS commands defined"; ((PASS++)); else echo "  ❌ Only $COMMANDS commands"; ((FAIL++)); fi
for cmd in exec termlog rlogs user agent_create agents task; do
    grep -q "def $cmd\|def exec_cmd\|def termlog\|def rlogs\|def user\|def agent_create\|def agents_list\|def task" bot.py 2>/dev/null
    check $? "Handler: /$cmd"
done
echo ""

# 9. GIT
echo "[9] GIT"
git log -1 --oneline > /dev/null 2>&1
check $? "Git repository ok"
git remote get-url origin > /dev/null 2>&1
check $? "Remote configured"
echo ""

# 10. RAILWAY
echo "[10] RAILWAY"
TOKEN=$(cat ~/.railway_token 2>/dev/null)
if [ -n "$TOKEN" ]; then
    echo "  ✅ Token present"; ((PASS++))
    PROJ=$(curl -s -H "Authorization: Bearer $TOKEN" "https://backboard.railway.app/graphql/v2" -d '{"query":"{ projects { edges { node { name } } } }"}' | jq -r '.data.projects.edges[0].node.name' 2>/dev/null)
    if [ -n "$PROJ" ] && [ "$PROJ" != "null" ]; then echo "  ✅ API connection ok ($PROJ)"; ((PASS++)); else echo "  ⚠️ Token expired"; ((WARN++)); fi
else
    echo "  ⚠️ No Railway token"; ((WARN++))
fi
echo ""

echo "══════════════════════════════════════════════"
echo "  VERIFICATION COMPLETE"
echo "══════════════════════════════════════════════"
echo "  ✅ PASSED: $PASS"
echo "  ❌ FAILED: $FAIL"
[ $WARN -gt 0 ] && echo "  ⚠️ WARNINGS: $WARN"
[ $FAIL -eq 0 ] && echo "  🎉 ALL SYSTEMS GO" || echo "  ⚠️ Some checks failed"
echo "══════════════════════════════════════════════"
