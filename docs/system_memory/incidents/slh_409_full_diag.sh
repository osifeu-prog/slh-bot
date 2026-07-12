#!/data/data/com.termux/files/usr/bin/bash

echo "======================================"
echo " SLH 409 FULL DIAGNOSTIC"
echo " $(date)"
echo "======================================"

echo
echo "===== 1. LOCAL PYTHON PROCESSES ====="
ps aux | grep -E "python|bot|slh|daemon|watchdog" | grep -v grep || echo "No local bot processes"

echo
echo "===== 2. LOCAL BOT FILE PROCESSES ====="
ps aux | grep "bot_stable.py" | grep -v grep || echo "No bot_stable local"

echo
echo "===== 3. TELEGRAM TOKEN TEST ====="
TOKEN=$(python3 - <<'PY'
import json
try:
    print(json.load(open("config.json"))["BOT_TOKEN"])
except Exception as e:
    print("")
PY
)

if [ -n "$TOKEN" ]; then
    curl -s "https://api.telegram.org/bot${TOKEN}/getMe"
else
    echo "NO TOKEN FOUND"
fi

echo
echo
echo "===== 4. TELEGRAM WEBHOOK ====="
curl -s "https://api.telegram.org/bot${TOKEN}/getWebhookInfo"

echo
echo
echo "===== 5. TELEGRAM GETUPDATES TEST ====="
curl -s "https://api.telegram.org/bot${TOKEN}/getUpdates?timeout=3"

echo
echo
echo "===== 6. RAILWAY STATUS ====="
railway status

echo
echo
echo "===== 7. RAILWAY DEPLOYMENTS ====="
railway deployment list | head -20

echo
echo
echo "===== 8. RAILWAY RECENT LOGS ====="
railway logs --tail 200 | grep -E \
"Starting Container|Stopping|Exited|Restart|LOCK|POLLING|409|ERROR|Traceback|RUNNING" \
|| echo "No matching logs"

echo
echo
echo "===== 9. DOCKER / RAILWAY START CONFIG ====="
echo "--- Dockerfile ---"
grep -n "ENTRYPOINT\|CMD" Dockerfile 2>/dev/null

echo "--- railway.json ---"
cat railway.json 2>/dev/null

echo
echo
echo "===== 10. LOCK IMPLEMENTATION ====="
grep -n \
"SLHLock\|acquire_lock\|release_lock\|LOCK_FILE" \
bot_stable.py slh_lock.py 2>/dev/null

echo
echo
echo "===== 11. TOKEN LOAD PATHS ====="
grep -n \
"BOT_TOKEN\|os.getenv\|config.json\|load_dotenv" \
bot_stable.py slh_lock.py 2>/dev/null | head -80

echo
echo
echo "===== 12. GIT STATE ====="
git status --short
git log -1 --oneline

echo
echo "======================================"
echo " END DIAGNOSTIC"
echo "======================================"
