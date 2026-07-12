#!/data/data/com.termux/files/usr/bin/bash

echo "===== SLH RUNTIME HANDLER TEST ====="

pkill -f bot_stable.py || true
rm -f .bot.lock

timeout 20 python3 bot_stable.py 2>&1 | tee runtime_handler_boot.log

echo
echo "===== LOADED ====="

grep -E "loaded|RUNNING|ERROR|Conflict|LOCK" runtime_handler_boot.log

echo
echo "===== COMMAND COUNT ====="

grep -R "@bot.message_handler(commands" -n . \
--exclude-dir=.git \
--exclude="*.pyc" | \
sed 's/.*commands=\[//' | sort | uniq -c | sort -nr | head -100

