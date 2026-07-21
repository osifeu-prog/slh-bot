#!/data/data/com.termux/files/usr/bin/bash

echo "======================================"
echo " SLH RUNTIME AUDIT"
echo "$(date)"
echo "======================================"

echo
echo "===== 1. LOCATION ====="
pwd
echo

echo "===== 2. FILE CHECK ====="
for f in bot_stable.py config.json Dockerfile railway.json Procfile state/db.json state/agents.json; do
    if [ -e "$f" ]; then
        echo "OK  $f"
    else
        echo "MISS $f"
    fi
done

echo
echo "===== 3. ENV SOURCES ====="

if [ -f ".env" ]; then
    echo "FOUND .env"
else
    echo "NO .env"
fi

if [ -f "state/.env" ]; then
    echo "FOUND state/.env"
else
    echo "NO state/.env"
fi

echo

echo "===== 4. TOKEN SEARCH (SAFE) ====="

grep -R "BOT_TOKEN" . \
--exclude-dir=.git \
--exclude-dir=pycache \
--exclude-dir=backups \
| head -30

echo

echo "===== 5. PYTHON TOKEN LOAD TEST ====="

python - <<'PY'
import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception as e:
    print("dotenv error:",e)

token=os.getenv("BOT_TOKEN")

if token:
    print("OK ENV TOKEN FOUND")
    print("TOKEN PREFIX:", token[:5])
else:
    print("NO ENV TOKEN")
PY

echo

echo "===== 6. CONFIG CHECK ====="

python - <<'PY'
import json, os

try:
    with open("config.json") as f:
        c=json.load(f)

    print("CONFIG OK")
    print("VERSION:",c.get("VERSION"))
    print("DB:",c.get("DB_FILE"))
    print("ADMIN:",c.get("SUPER_ADMIN"))

    if "BOT_TOKEN" in c:
        print("WARNING: TOKEN IN CONFIG")
    else:
        print("CONFIG CLEAN")

except Exception as e:
    print("CONFIG ERROR:",e)
PY

echo

echo "===== 7. RAILWAY LINK ====="

if command -v railway >/dev/null; then
    railway status
else
    echo "Railway CLI missing"
fi

echo

echo "===== 8. RAILWAY VARIABLES CHECK ====="

if command -v railway >/dev/null; then
    railway variables | grep -E "BOT_TOKEN|RAILWAY_STOP_BOT|RAILWAY_ENVIRONMENT|SERVICE"
else
    echo "skip"
fi

echo

echo "===== 9. BOT PROCESS LOCAL ====="

ps aux | grep -E "bot_stable|python" | grep -v grep || echo "No local bot"

echo

echo "===== 10. POLLING CODE CHECK ====="

grep -nE "start_polling|run_polling|getUpdates|delete_webhook" bot_stable.py | head -30

echo

echo "===== 11. DUPLICATE POLLER SEARCH ====="

ps aux | grep -E "bot|python" | grep -v grep

echo

echo "===== COMPLETE ====="
