#!/data/data/com.termux/files/usr/bin/bash

echo "🛡️ SLH PRE-CHANGE SAFETY CHECK"
echo "=============================="

# 1. בדיקת קבצים קריטיים
echo ""
echo "📁 Checking core files..."

FILES=("bot_stable.py" "state/system.json" "state/progress.json" "dna_lock.py" "safe_progress.py")

for f in "${FILES[@]}"; do
  if [ -f "$f" ]; then
    echo "✔ $f OK"
  else
    echo "❌ $f MISSING"
  fi
done

# 2. בדיקת תהליכים
echo ""
echo "⚙️ Running processes..."
pgrep -af bot_stable.py || echo "ℹ️ Bot not running"

# 3. בדיקת פורמט Python (קריטי)
echo ""
echo "🐍 Python syntax check..."

python3 -m py_compile bot_stable.py
if [ $? -eq 0 ]; then
  echo "✔ bot_stable.py syntax OK"
else
  echo "❌ bot_stable.py has syntax errors"
  exit 1
fi

# 4. בדיקת JSON
echo ""
echo "🧾 JSON validation..."

for f in state/*.json; do
  python3 -c "import json; json.load(open('$f'))" 2>/dev/null
  if [ $? -eq 0 ]; then
    echo "✔ $f OK"
  else
    echo "❌ $f BROKEN JSON"
  fi
done

# 5. בדיקת כפילויות בסיסית
echo ""
echo "🔍 Duplicate risk scan..."

grep -R "TeleBot" bot_stable.py | wc -l | awk '{print "TeleBot references:", $1}'
grep -R "patch(bot)" bot_stable.py | wc -l | awk '{print "Patch hooks:", $1}'

# 6. סיכום
echo ""
echo "=============================="
echo "✅ PRE-CHECK COMPLETE"
echo "If no ❌ errors → SAFE TO MODIFY"
