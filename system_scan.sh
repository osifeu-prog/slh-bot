#!/data/data/com.termux/files/usr/bin/bash

echo "========================================"
echo " SLH SYSTEM SCAN"
echo "========================================"

echo
echo "1. Current directory"
pwd

echo
echo "2. Python processes"
ps aux | grep python | grep -v grep

echo
echo "3. Bot processes"
ps aux | grep bot.py | grep -v grep

echo
echo "4. Project tree"
find . -maxdepth 2 -type f | sort

echo
echo "5. Python files"
find . -name "*.py" | sort

echo
echo "6. Telegram handlers"
grep -R "@bot.message_handler" . 2>/dev/null

echo
echo "7. TeleBot objects"
grep -R "TeleBot(" . 2>/dev/null

echo
echo "8. ControlLayer"
grep -R "class ControlLayer" . 2>/dev/null

echo
echo "9. SLHCore"
grep -R "class SLHCore" . 2>/dev/null

echo
echo "10. Queue usage"
grep -R "Queue(" . 2>/dev/null

echo
echo "11. Config usage"
grep -R "config.json" . 2>/dev/null

echo
echo "12. Boot files"
grep -R "__main__" . 2>/dev/null

echo
echo "13. Git status"
git status --short 2>/dev/null

echo
echo "========================================"
echo "SCAN COMPLETE"
echo "========================================"
