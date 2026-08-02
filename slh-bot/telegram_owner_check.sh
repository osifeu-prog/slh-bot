#!/data/data/com.termux/files/usr/bin/bash

echo "=============================="
echo "TELEGRAM OWNER CHECK"
echo "$(date)"
echo "=============================="

echo
echo "=== LOCAL ==="
ps aux | grep -E "python|bot|SLH" | grep -v grep

echo
echo "=== RAILWAY LOG LAST STARTS ==="
railway logs --tail 500 | grep -E "POLLLING|POLLING|Starting|Started|BOOT|python|Traceback|409|Conflict"

echo
echo "=== BOT ENTRY POINTS ==="

grep -n "bot.infinity_polling" bot_stable.py

echo
echo "=== ALL TELEGRAM CALLS ==="

grep -RIn "infinity_polling\|polling(" . \
--exclude-dir=archive \
--exclude-dir=backup \
--exclude-dir=backups

echo
echo "=== LOCK STATUS ==="

cat .bot.lock 2>/dev/null || echo "NO LOCK"

echo
echo "DONE"

