#!/data/data/com.termux/files/usr/bin/bash


cd ~/slh_clean || exit 1

# Load SLH environment
if [ -f "state/.env" ]; then
    source state/.env
    echo "✅ state/.env loaded"
else
    echo "⚠️ state/.env missing"
fi

mkdir -p logs runtime

echo "==== SLH SECURE START ===="

if [ -f runtime/bot.pid ]; then
    OLD=$(cat runtime/bot.pid 2>/dev/null)

    if kill -0 "$OLD" 2>/dev/null; then
        echo "❌ BOT ALREADY RUNNING PID=$OLD"
        exit 1
    fi
fi

echo "Starting bot..."

nohup python3 -u -B bot_stable.py \
    > logs/bot.log \
    2> logs/error.log &

PID=$!

echo "$PID" > runtime/bot.pid

sleep 3

echo "===== PROCESS ====="
pgrep -af bot_stable.py || echo "BOT NOT RUNNING"

echo "===== PID ====="
cat runtime/bot.pid
