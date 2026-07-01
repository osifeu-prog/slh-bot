#!/bin/bash
echo "════════════════════════════════════════"
echo "🔍 SLH FULL DIAGNOSTIC"
echo "════════════════════════════════════════"
echo "Date: $(date)"
echo ""

echo "1. Processes:"
pgrep -af "python"  echo "No python processes"

echo ""
echo "2. DB Status:"
ls -la db.json state/db.json 2>/dev/null  echo "No DB"
cat db.json 2>/dev/null | python3 -m json.tool | head -20  echo "Invalid JSON"

echo ""
echo "3. Bot Log:"
tail -30 bot.log 2>/dev/null | tail -15  echo "No bot.log"

echo ""
echo "4. Syntax:"
python3 -m py_compile bot_stable.py && echo "✅ bot_stable.py OK"  echo "❌ Syntax Error"

echo ""
echo "5. Handlers:"
grep -c "@bot.message_handler" bot_stable.py course_handlers.py  echo "No handlers"

echo ""
echo "6. Restart:"
pkill -9 -f "python.*bot" 2>/dev/null
sleep 3
nohup python3 bot_stable.py > bot.log 2>&1 &
echo "✅ Restarted"
sleep 5
pgrep -af "python.*bot" || echo "Still not running"
