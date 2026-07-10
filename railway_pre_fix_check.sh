#!/data/data/com.termux/files/usr/bin/bash

echo "===== RAILWAY PRE FIX CHECK ====="

echo
echo "=== railway.json ==="
cat railway.json 2>/dev/null

echo
echo "=== Procfile ==="
cat Procfile 2>/dev/null || echo "NO Procfile"

echo
echo "=== bot start area ==="
sed -n '1300,1410p' bot_stable.py

echo
echo "=== imports top ==="
head -80 bot_stable.py

echo
echo "=== health import search ==="
grep -RIn "railway_health\|start_health_server\|Flask" *.py

echo
echo "=== polling locations ==="
grep -RIn "infinity_polling\|polling" . --exclude-dir=archive --exclude-dir=.git

echo
echo "=== Railway processes from logs ==="
tail -100 bot_stable.log 2>/dev/null
tail -100 bot.log 2>/dev/null

echo
echo "===== END CHECK ====="
