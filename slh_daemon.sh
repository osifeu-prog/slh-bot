#!/data/data/com.termux/files/usr/bin/bash

cd ~/slh_clean

echo "🚀 SLH OS Daemon started – $(date)"

mkdir -p runtime

# stop old bot instances only
pkill -f "python3.*bot_stable.py" 2>/dev/null

sleep 1

# Bot
nohup python3 -B bot_stable.py >> bot.log 2>&1 &

BOT_PID=$!

echo $BOT_PID > runtime/bot.pid

echo "  ✅ Bot started PID=$BOT_PID"


# API
pkill -f "web/api/app.py" 2>/dev/null

nohup python3 web/api/app.py >> web.log 2>&1 &

echo "  ✅ API started"


# Dashboard
pkill -f "http.server 8000" 2>/dev/null

nohup python3 -m http.server 8000 -d web/dashboard >> /dev/null 2>&1 &

echo "  ✅ Dashboard started"


sleep 3

echo ""
echo "=== SLH STATUS ==="

ps aux | grep -E "bot_stable|web/api|http.server" | grep -v grep

echo ""
echo "✅ ALL SERVICES STARTED"

