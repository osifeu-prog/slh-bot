#!/data/data/com.termux/files/usr/bin/bash

echo "=== SLH HEALTH ==="

if pgrep -f bot_stable.py > /dev/null; then
  echo "BOT: RUNNING"
else
  echo "BOT: DOWN"
fi

echo "PID:"
cat runtime/bot.pid 2>/dev/null || echo "NO PID"

echo ""
echo "LAST ERRORS:"
tail -n 5 logs/error.log 2>/dev/null

echo "=================="
