#!/data/data/com.termux/files/usr/bin/bash

echo "================================="
echo "🧠 SLH FULL DIAGNOSTIC"
echo "$(date)"
echo "================================="

echo
echo "=== 1. LOCAL PROCESSES ==="
ps aux | grep -E "python|bot|SLH|daemon" | grep -v grep || true

echo
echo "=== 2. LOCK FILES ==="
find . -maxdepth 2 -type f \( -name "*.lock" -o -name "*lock*" \) -print -exec cat {} \; 2>/dev/null || true

echo
echo "=== 3. BOT ENTRYPOINTS ==="
grep -RIn "infinity_polling\|polling\|getUpdates\|while True" . \
--exclude-dir=.git \
--exclude-dir=archive \
--exclude-dir=backup \
--exclude-dir=backups 2>/dev/null || true

echo
echo "=== 4. WEBHOOK STATUS ==="
if [ -f config.json ]; then
TOKEN=$(grep -o '"BOT_TOKEN"[[:space:]]*:[[:space:]]*"[^"]*"' config.json | sed 's/.*"//;s/"$//')
if [ ! -z "$TOKEN" ]; then
curl -s "https://api.telegram.org/bot$TOKEN/getWebhookInfo"
echo
else
echo "TOKEN NOT FOUND IN config.json"
fi
else
echo "config.json missing"
fi

echo
echo "=== 5. TELEGRAM POLLING CODE ==="
grep -RIn "infinity_polling\|polling" . \
--exclude-dir=.git \
--exclude-dir=archive \
--exclude-dir=backup \
--exclude-dir=backups 2>/dev/null || true

echo
echo "=== 6. SLH CORE FILES ==="
ls -la core 2>/dev/null || true

echo
echo "=== 7. RUNTIME / KERNEL REFERENCES ==="
grep -RIn "Runtime\|Kernel\|EventBus\|SLH_MAIN\|SLH_GATEWAY" . \
--exclude-dir=.git \
--exclude-dir=archive \
--exclude-dir=backup \
--exclude-dir=backups 2>/dev/null || true

echo
echo "=== 8. PYTHON IMPORT CHECK ==="
python - <<'PY'
mods=[
"core.kernel",
"core.runtime",
"core.event_bus",
"core.dispatcher",
"core.telegram_router_bridge"
]

for m in mods:
    try:
        __import__(m)
        print("OK ",m)
    except Exception as e:
        print("FAIL",m,repr(e))
PY

echo
echo "=== 9. RAILWAY STATUS ==="
if command -v railway >/dev/null; then
railway status
else
echo "railway CLI missing"
fi

echo
echo "=== 10. RAILWAY RECENT ERRORS ==="
if command -v railway >/dev/null; then
railway logs --tail 150 | grep -E "409|Conflict|ERROR|Exception|Traceback|Started|Starting|Stopping|Exited" || true
fi

echo
echo "=== 11. BOT SIZE / TIMESTAMP ==="
ls -lh bot_stable.py SLH_MAIN.py SLH_KERNEL.py 2>/dev/null || true

echo
echo "=== 12. GIT STATE ==="
git status --short 2>/dev/null || true

echo
echo "================================="
echo "✅ DIAGNOSTIC COMPLETE"
echo "================================="
