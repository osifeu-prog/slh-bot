#!/data/data/com.termux/files/usr/bin/bash

echo "===== SLH COMMAND MAP ====="

grep -R "@bot.message_handler(commands" -n . \
--exclude-dir=.git \
--exclude-dir=state \
--exclude-dir=backups \
--exclude="*.pyc" \
2>/dev/null | sort

echo
echo "===== REGISTER / INIT ====="

grep -R "init(bot\|register_" -n . \
--exclude-dir=.git \
--exclude-dir=state \
--exclude-dir=backups \
--exclude="*.pyc" \
2>/dev/null | sort

echo
echo "===== DUPLICATE COMMANDS ====="

grep -R "@bot.message_handler(commands" -h . \
--exclude-dir=.git \
--exclude-dir=state \
--exclude-dir=backups \
--exclude="*.pyc" \
2>/dev/null \
| sed -E "s/.*commands=\[['\"]([^'\"]+).*/\1/" \
| sort | uniq -d

echo
echo "===== DONE ====="
