#!/usr/bin/env bash
# SLH OS – Morning Startup
cd ~/slh_clean

echo "=== START DAY $(date) ==="

echo ""
echo "📜 AGENT RULES:"
cat AGENT_RULES.md

echo ""
echo "📜 SYSTEM RULES:"
cat SYSTEM_RULES.md

echo ""
echo "📜 KERNEL RULES:"
cat KERNEL_RULES.md

echo ""
echo "📜 SOURCE OF TRUTH:"
cat SOURCE_OF_TRUTH.md

echo ""
echo "📓 Journal (last 5 entries):"
python3 -c "
import json
j=json.load(open('journal.json'))
for e in j[-5:]: print(e.get('time','?'), e.get('text','')[:100])
"

echo ""
echo "🚆 Railway Status:"
railway status

echo ""
echo "💾 DB Snapshot:"
python3 -c "
import json
db=json.load(open('state/db.json'))
print('users:', len(db.get('users',{})))
print('agents:', len(db.get('agents',{})))
print('tasks:', len(db.get('tasks',{})))
"

echo ""
echo "🟢 Ready to work."
