#!/data/data/com.termux/files/usr/bin/bash

while true
do
  echo "🚀 START BOT $(date)"

  python3 bot_fix.py

  echo "⚠️ BOT CRASHED - restarting in 3 seconds..."
  sleep 3
done
