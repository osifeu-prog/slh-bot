#!/data/data/com.termux/files/usr/bin/bash
cd ~/slh_clean
while true; do
    python3 -B bot.py >> bot.log 2>&1
    echo "$(date): Bot crashed, restarting in 5s..." >> bot.log
    sleep 5
done
