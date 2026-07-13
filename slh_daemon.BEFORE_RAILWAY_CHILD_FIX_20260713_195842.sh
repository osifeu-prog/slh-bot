#!/data/data/com.termux/files/usr/bin/bash

cd ~/slh_clean

mkdir -p runtime

if [ "$1" = "stop" ]; then

    echo "🛑 Stopping SLH services..."

    if [ -f runtime/bot.pid ]; then
        PID=$(cat runtime/bot.pid)

        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID"
            echo "✅ Bot stopped PID=$PID"
        fi

        rm -f runtime/bot.pid
    fi

    pkill -f "web/api/app.py" 2>/dev/null || true
    pkill -f "http.server 8000" 2>/dev/null || true

    rm -f .bot.lock

    echo "✅ SLH stopped cleanly"
    exit 0
fi


echo "🚀 SLH OS Daemon started – $(date)"


# prevent duplicates
pkill -f "python3.*bot_stable.py" 2>/dev/null || true
sleep 2


nohup railway run python3 -u -B bot_stable.py >> bot.log 2>&1 &

BOT_PID=$!

echo "$BOT_PID" > runtime/bot.pid

echo "  ✅ Bot started PID=$BOT_PID"


pkill -f "web/api/app.py" 2>/dev/null || true

nohup python3 web/api/app.py >> web.log 2>&1 &

echo "  ✅ API started"


pkill -f "http.server 8000" 2>/dev/null || true

nohup python3 -m http.server 8000 -d web/dashboard >> /dev/null 2>&1 &

echo "  ✅ Dashboard started"


sleep 3

echo ""
echo "=== SLH STATUS ==="

ps aux | grep -E "bot_stable|web/api|http.server" | grep -v grep

echo ""
echo "✅ ALL SERVICES STARTED"
