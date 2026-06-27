#!/data/data/com.termux/files/usr/bin/bash

while true
do
  if ! pgrep -f bot_fix.py > /dev/null
  then
    echo "🧯 BOT NOT RUNNING - restarting..."
    cd ~/slh_clean
    nohup ./run_bot.sh > bot.log 2>&1 &
  fi

  sleep 5
done
