#!/usr/bin/env bash
cd ~/slh_clean
if ! pgrep -f bot_stable.py >/dev/null; then
    echo "$(date) Bot down, restarting..." >> logs/healthcheck.log
    ./start.sh
fi
