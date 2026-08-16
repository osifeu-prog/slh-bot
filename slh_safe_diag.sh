#!/data/data/com.termux/files/usr/bin/bash

echo "=============================="
echo "🧠 SLH SAFE DIAG"
echo "$(date)"
echo "=============================="

echo
echo "=== PROCESSES ==="
ps aux | grep -E "python|bot|SLH|daemon" | grep -v grep

echo
echo "=== BOT POLLING ==="
grep -n "infinity_polling\|getUpdates\|while True" bot_stable.py 2>/dev/null

echo
echo "=== LOCK ==="
grep -RIn "SLHLock\|acquire_lock\|release_lock" . --include="*.py" 2>/dev/null

echo
echo "=== WEBHOOK ==="
python3 - <<'PY'
import os, json, requests

try:
    with open("config.json") as f:
        c=json.load(f)

    token=c.get("BOT_TOKEN")

    if token:
        r=requests.get(
            f"https://api.telegram.org/bot{token}/getWebhookInfo",
            timeout=10
        )
        print(r.json())
    else:
        print("NO TOKEN")
except Exception as e:
    print("WEBHOOK CHECK ERROR",e)
PY

echo
echo "=== CORE FILES ==="
ls -lh core 2>/dev/null

echo
echo "=== MAIN FILES ==="
ls -lh bot_stable.py SLH_MAIN.py SLH_KERNEL.py 2>/dev/null

echo
echo "=== IMPORT TEST ==="
python3 - <<'PY'
for m in [
"core.kernel",
"core.runtime",
"core.event_bus",
"core.dispatcher"
]:
    try:
        __import__(m)
        print("OK",m)
    except Exception as e:
        print("FAIL",m,e)
PY

echo
echo "=== DONE ==="
