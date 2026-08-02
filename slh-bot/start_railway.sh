#!/bin/bash
set -e

echo "נ€ Starting SLH Railway runtime"

if [ -f /tmp/slh_railway.lock ]; then
    echo "ג Another runtime already exists"
    exit 1
fi

touch /tmp/slh_railway.lock

cleanup() {
    rm -f /tmp/slh_railway.lock
    kill $API_PID $BOT_PID 2>/dev/null || true
}

trap cleanup SIGTERM SIGINT EXIT

python3 -u web/api/app.py &
API_PID=$!

echo "נ API PID=$API_PID"

python3 -u -B bot_stable.py &
BOT_PID=$!

echo "נ₪– BOT PID=$BOT_PID"

wait -n $API_PID $BOT_PID
# checkpoint
