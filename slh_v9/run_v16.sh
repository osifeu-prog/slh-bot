#!/data/data/com.termux/files/usr/bin/bash

echo "🚀 STARTING SWARM V16 DAEMON"

cd ~/slh_clean/slh_v9

while true; do
    python swarm_v16.py
    echo "⚠️ CRASH DETECTED - RESTARTING IN 2s"
    sleep 2
done
