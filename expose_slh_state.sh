#!/data/data/com.termux/files/usr/bin/bash

echo "========== SLH SYSTEM SNAPSHOT =========="
date

echo
echo "========== CURRENT DIR =========="
pwd

echo
echo "========== GIT STATUS =========="
git status 2>/dev/null || echo "NO GIT"

echo
echo "========== GIT LOG =========="
git log --oneline -5 2>/dev/null || true

echo
echo "========== ROOT FILES =========="
ls -la | sed -n '1,120p'

echo
echo "========== HANDLERS =========="
find handlers -maxdepth 2 -type f 2>/dev/null | sort

echo
echo "========== CORE =========="
find core -maxdepth 2 -type f 2>/dev/null | sort

echo
echo "========== SERVICES =========="
find services -maxdepth 2 -type f 2>/dev/null | sort

echo
echo "========== AGENTS =========="
find agents -maxdepth 3 -type f 2>/dev/null | sort

echo
echo "========== WEB =========="
find web -maxdepth 3 -type f 2>/dev/null | sort

echo
echo "========== IMPORTANT PYTHON ENTRY FILES =========="
ls -1 bot*.py run*.py SLH*.py main*.py 2>/dev/null

echo
echo "========== REQUIREMENTS =========="
cat requirements.txt 2>/dev/null || true

echo
echo "========== ENV KEYS ONLY =========="
if [ -f .env ]; then
    sed 's/=.*$/=***HIDDEN***/' .env
else
    echo "NO .env"
fi

echo
echo "========== CONFIG KEYS =========="
if [ -f config.json ]; then
    python3 - <<'PY'
import json
try:
    d=json.load(open("config.json"))
    print(list(d.keys()))
except Exception as e:
    print(e)
PY
fi

echo
echo "========== PROCESSES =========="
ps -ef | grep -E "bot|python|SLH|uvicorn|http" | grep -v grep

echo
echo "========== PORTS =========="
ss -tulpn 2>/dev/null || netstat -tulpn 2>/dev/null || true

echo
echo "========== DAEMON =========="
ls -la slh_daemon.sh start.sh start_slh.sh 2>/dev/null

echo
echo "========== SNAPSHOTS =========="
find . -maxdepth 3 -iname "*snapshot*" -o -iname "*backup*" | sort | tail -50

echo
echo "========== RAILWAY/Docker =========="
ls -la Dockerfile railway.toml docker-compose.yml Procfile 2>/dev/null

echo
echo "========== COMPILE CHECK =========="
python3 -m py_compile bot_stable.py 2>&1

echo
echo "========== END SNAPSHOT =========="
