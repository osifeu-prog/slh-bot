#!/data/data/com.termux/files/usr/bin/bash

echo "================================="
echo " SLH PRODUCTION RECOVERY CHECK"
echo "================================="

date

echo ""
echo "=== PROCESS CHECK ==="
ps aux | grep -E "bot_stable|python" | grep -v grep

echo ""
echo "=== PID LOCK ==="
if [ -f runtime/bot.pid ]; then
    echo "PID FILE:"
    cat runtime/bot.pid
    PID=$(cat runtime/bot.pid)
    kill -0 $PID 2>/dev/null && echo "✅ PID ACTIVE" || echo "⚠️ PID DEAD"
else
    echo "⚠️ NO PID FILE"
fi


echo ""
echo "=== TELEGRAM TOKEN TEST ==="

python3 - <<'PY'
from pathlib import Path
import json, os

token=""

try:
    cfg=json.loads(Path("state/config.json").read_text())
    token=cfg.get("BOT_TOKEN","")
except:
    pass

if not token:
    token=os.getenv("BOT_TOKEN","")

if ":" in token:
    print("✅ TOKEN FORMAT OK")
else:
    print("❌ TOKEN INVALID")
PY


echo ""
echo "=== IMPORT TEST ==="

python3 - <<'PY'
mods=[
"bot_stable",
"advanced_ask_handler",
"doctor_handler",
"welcome_handler",
"handlers.llm_handler"
]

for m in mods:
    try:
        __import__(m)
        print("✅",m)
    except Exception as e:
        print("❌",m,e)
PY


echo ""
echo "=== POLLING LOCATIONS ==="

grep -R "infinity_polling\|polling(" -n . \
--include="*.py" \
| grep -v __pycache__


echo ""
echo "=== MARKDOWN RISK ==="

grep -R "parse_mode" -n . \
--include="*.py" \
| grep -v __pycache__


echo ""
echo "=== LLM ENV ==="

python3 - <<'PY'
import os

for x in [
"GROQ_API_KEY",
"GEMINI_API_KEY",
"BOT_TOKEN"
]:
    print(x, "OK" if os.getenv(x) else "MISSING")
PY


echo ""
echo "=== RAILWAY LIVE ==="

railway logs --tail 80 2>/dev/null \
| grep -E "RUNNING|POLLING|ERROR|Exception|Conflict|loaded"


echo ""
echo "================================="
echo " RECOVERY CHECK COMPLETE"
echo "================================="

