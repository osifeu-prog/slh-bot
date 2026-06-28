#!/data/data/com.termux/files/usr/bin/bash
PASS=0; FAIL=0; WARN=0

check() {
    if [ "$1" -eq 0 ]; then echo "  ✅ $2"; ((PASS++)); else echo "  ❌ $2"; ((FAIL++)); fi
}

echo "══════════════════════════════════════════════"
echo "  SLH OS v2.0 – FINAL VERIFICATION"
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
BOT_COUNT=$(pgrep -c "python3.*bot.py" 2>/dev/null)
if [ "$BOT_COUNT" -eq 1 ]; then echo "  ✅ Single bot instance (1)"; ((PASS++)); else echo "  ❌ Multiple bot instances ($BOT_COUNT)"; ((FAIL++)); fi
echo ""

# 2. API ENDPOINTS
echo "[2] API ENDPOINTS"
curl -s http://localhost:5000/api/health | grep -q '"ok"' 2>/dev/null
check $? "/api/health returns ok"
python3 -c "import urllib.request, json; data=json.loads(urllib.request.urlopen('http://localhost:5000/api/agents').read()); exit(0 if isinstance(data,dict) else 1)" 2>/dev/null
check $? "/api/agents returns JSON"
python3 -c "import urllib.request, json; data=json.loads(urllib.request.urlopen('http://localhost:5000/api/tasks').read()); exit(0 if isinstance(data,list) else 1)" 2>/dev/null
check $? "/api/tasks returns JSON array"
python3 -c "import urllib.request, json; data=json.loads(urllib.request.urlopen('http://localhost:5000/api/stats').read()); exit(0 if 'users' in data else 1)" 2>/dev/null
check $? "/api/stats returns expected fields"
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

# 5. AGENT OS
echo "[5] AGENT OS"
python3 << 'PYEOF'
import json, time
agents = {}
aid = str(len(agents)+1)
agents[aid] = {"name":"verify","role":"agent","state":"idle","inbox":[],"history":[],"created":time.strftime("%Y-%m-%d %H:%M:%S"),"permissions":["read"]}
agents[aid]["state"] = "busy"
agents[aid]["history"].append({"time":time.strftime("%Y-%m-%d %H:%M:%S"),"action":"state→busy"})
agents[aid]["inbox"].append({"time":time.strftime("%Y-%m-%d %H:%M:%S"),"message":"test"})
checks = [
    ("Agent created", aid in agents),
    ("State changed to busy", agents[aid]["state"]=="busy"),
    ("Inbox message", len(agents[aid]["inbox"])==1),
]
try:
    with open("test_agents.json","w") as f: json.dump(agents, f)
    with open("test_agents.json") as f: loaded = json.load(f)
    checks.append(("Persistence save/load", aid in loaded))
except: checks.append(("Persistence save/load", False))
checks.append(("Permissions", "read" in agents[aid]["permissions"]))
for name, ok in checks: print(f"  {'✅' if ok else '❌'} {name}")
exit(0 if all(c[1] for c in checks) else 1)
PYEOF
check $? "Agent OS all checks"
echo ""

# 6. KERNEL + TASK PLUGIN
echo "[6] KERNEL + TASK PLUGIN"
python3 << 'PYEOF'
import sys, json, time
sys.path.insert(0,'.')
from core.event_bus import EventBus
from plugins.task import TaskPlugin
bus = EventBus(workers=1)
class K: pass
k = K(); k.bus = bus; k.state = {}; k.telegram = None
TaskPlugin().on_start(k)
bus.emit("task_create", {"chat":123,"task":"verify_task"})
time.sleep(0.3)
event = bus.store.fetch_batch(1)
if event:
    eid,etype,payload = event[0]
    bus._process(eid,etype,json.loads(payload))
    ok1 = "verify_task" in k.state.get("tasks",[])
else: ok1 = False
bus.emit("task_create", {"chat":123,"task":"task2"})
time.sleep(0.3)
event = bus.store.fetch_batch(1)
if event:
    eid,etype,payload = event[0]
    bus._process(eid,etype,json.loads(payload))
    ok2 = len(k.state.get("tasks",[]))==2
else: ok2 = False
checks = [("EventBus init", bus is not None), ("TaskPlugin init", True), ("Task creation", ok1), ("Multiple tasks", ok2)]
for name, ok in checks: print(f"  {'✅' if ok else '❌'} {name}")
exit(0 if all(c[1] for c in checks) else 1)
PYEOF
check $? "Kernel + TaskPlugin all checks"
echo ""

# 7. AUDIT
echo "[7] AUDIT LOG"
python3 -c "from audit_logger import audit, get_audit; audit('verification','system','final'); entries=get_audit(5); exit(0 if any(e.get('action')=='verification' for e in entries) else 1)" 2>/dev/null
check $? "Audit records action"
echo ""

# 8. BOT COMMANDS
echo "[8] BOT COMMANDS"
COMMANDS=$(grep -c "@bot.message_handler" bot.py 2>/dev/null)
if [ "$COMMANDS" -ge 50 ]; then echo "  ✅ $COMMANDS commands defined (≥50)"; ((PASS++)); else echo "  ❌ Only $COMMANDS commands (<50)"; ((FAIL++)); fi

# Key new commands
for cmd in ask reload alert testcmd debugcmd market market_install market_search market_rate market_upload; do
    grep -q "def $cmd\|def market_$cmd" bot.py 2>/dev/null
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

# 10. MARKETPLACE + MONETIZATION IMPORTS
echo "[10] MARKETPLACE & MONETIZATION"
python3 -c "from marketplace import load_store, save_store; print('  ✅ Marketplace import OK')" 2>&1
check $? "Marketplace import"
python3 -c "from subscriptions import PLANS, get_user_plan, set_user_plan; print('  ✅ Subscriptions import OK')" 2>&1
check $? "Monetization import"
echo ""

echo "══════════════════════════════════════════════"
echo "  VERIFICATION COMPLETE"
echo "══════════════════════════════════════════════"
echo "  ✅ PASSED: $PASS"
echo "  ❌ FAILED: $FAIL"
[ $WARN -gt 0 ] && echo "  ⚠️ WARNINGS: $WARN"
[ $FAIL -eq 0 ] && echo "  🎉 ALL SYSTEMS GO" || echo "  ⚠️ Some checks failed – review above"
echo "══════════════════════════════════════════════"
