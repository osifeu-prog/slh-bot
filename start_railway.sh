#!/bin/bash
set -e

echo "🚀 Starting SLH Railway runtime"

python3 -u web/api/app.py &
API_PID=$!

echo "🌐 API PID=$API_PID"

python3 -u -B bot_stable.py &
BOT_PID=$!

echo "🤖 BOT PID=$BOT_PID"

trap "kill $API_PID $BOT_PID" SIGTERM SIGINT

wait -n $API_PID $BOT_PID
