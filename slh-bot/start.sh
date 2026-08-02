#!/data/data/com.termux/files/usr/bin/bash

cd ~/slh_clean || exit 1

pkill -f bot_stable.py 2>/dev/null
pkill -f python3 2>/dev/null
sleep 2

rm -f runtime/bot.pid /tmp/slh.lock

echo "START BOT..."

nohup python3 -u bot_stable.py > logs/bot.log 2> logs/error.log &
echo $! > runtime/bot.pid

sleep 3
pgrep -af bot_stable.py || echo "NOT RUNNING"
