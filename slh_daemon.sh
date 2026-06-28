#!/data/data/com.termux/files/usr/bin/bash
export BOT_TOKEN=$(python3 -c "import json; print(json.load(open("config.json"))["BOT_TOKEN"])")
cd ~/slh_clean

echo "🚀 SLH OS Daemon started – $(date)"

# 1. Bot
pkill -f "python3.*bot.py" 2>/dev/null
nohup python3 -B bot.py >> bot.log 2>&1 &
echo "  ✅ Bot started"

# 2. API
pkill -f "web/api/app.py" 2>/dev/null
nohup python3 web/api/app.py >> web.log 2>&1 &
echo "  ✅ API started"

# 3. Dashboard
pkill -f "http.server 8000" 2>/dev/null
nohup python3 -m http.server 8000 -d web/dashboard >> /dev/null 2>&1 &
echo "  ✅ Dashboard started"

sleep 2
echo "  ✅ All services running"
