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


if [ "$1" = "--with-bot" ]; then
    echo "⚠️  --with-bot flag detected: starting bot_stable.py LOCALLY."
    echo "⚠️  This WILL conflict with Railway (409 Conflict) unless Railway is stopped"
    echo "⚠️  or this Termux instance uses a separate BOT_TOKEN. See DO_NOT_RUN_LOCALLY.md"
    pkill -f "python3.*bot_stable.py" 2>/dev/null || true
    sleep 2
    nohup python3 -u -B bot_stable.py >> bot.log 2>&1 &
    BOT_PID=$!
    echo "$BOT_PID" > runtime/bot.pid
    echo "  ✅ Bot started locally PID=$BOT_PID"
else
    echo "  ℹ️  Skipping local bot_stable.py (Railway is production)."
    echo "  ℹ️  Use './slh_daemon.sh start --with-bot' to override. See DO_NOT_RUN_LOCALLY.md"
fi


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

# --- Auto-validate handlers before start ---
echo "🔍 Checking handler syntax..."
python3 -m compileall handlers/ >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "❌ Handler syntax warning – aborting start."
    exit 1
fi
echo "✅ All handlers valid"
