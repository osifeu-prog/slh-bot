#!/usr/bin/env bash
# SLH OS – End-of-Day Snapshot & Journal Update
cd ~/slh_clean

echo "=== SNAPSHOT $(date) ===" > state/end_of_day_log.txt
echo "" >> state/end_of_day_log.txt

echo "--- Railway Status ---" >> state/end_of_day_log.txt
railway status >> state/end_of_day_log.txt 2>&1

echo "" >> state/end_of_day_log.txt
echo "--- Git Log (last 3) ---" >> state/end_of_day_log.txt
git log -3 --oneline >> state/end_of_day_log.txt 2>&1

echo "" >> state/end_of_day_log.txt
echo "--- DB Stats ---" >> state/end_of_day_log.txt
python3 -c "
import json
db=json.load(open('state/db.json'))
print('users:', len(db.get('users',{})))
print('agents:', len(db.get('agents',{})))
print('tasks:', len(db.get('tasks',{})))
" >> state/end_of_day_log.txt 2>&1

echo "" >> state/end_of_day_log.txt
echo "--- Agents file ---" >> state/end_of_day_log.txt
python3 -c "
import json
a=json.load(open('state/agents.json'))
print('agents:', len(a))
" >> state/end_of_day_log.txt 2>&1

echo "" >> state/end_of_day_log.txt
echo "--- Journal last 5 ---" >> state/end_of_day_log.txt
python3 -c "
import json
j=json.load(open('journal.json'))
for e in j[-5:]: print(e.get('time','?'), e.get('text','')[:80])
" >> state/end_of_day_log.txt 2>&1

echo "✅ Snapshot saved"

# Add and push if changes
git add state/end_of_day_log.txt journal.json state/*.json 2>/dev/null
if git diff --cached --quiet; then
    echo "✅ Nothing new to commit"
else
    git commit -m "End-of-day snapshot $(date +%Y-%m-%d)"
    git push
    echo "🚀 Pushed to GitHub"
fi
