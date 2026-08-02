#!/bin/sh

echo "==== SLH CONTAINER START ===="

echo "Starting API..."
python3 -u /app/web/api/app.py > /app/web.log 2>&1 &

API_PID=$!

echo "API PID=$API_PID"

sleep 2

echo "Starting BOT..."
python3 -u -B /app/bot_stable.py

echo "BOT EXITED"
