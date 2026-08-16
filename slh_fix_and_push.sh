#!/bin/bash
echo "🔧 SLH FIX & PUSH – starting"

# 1. תיקון תלויות
pip install --upgrade pip setuptools wheel 2>/dev/null
pip install groq paho-mqtt 2>/dev/null

# 2. תיקון BOM
python3 -c "
from pathlib import Path
p = Path('state/monitor_config.json')
if p.exists():
    p.write_text(p.read_text(encoding='utf-8-sig'), encoding='utf-8')
    print('✅ BOM removed')
"

# 3. עטיפת ייבוא esp_handler (לא קריטי)
sed -i 's/from handlers\.esp_handler import register_esp_handler/try:\n    from handlers.esp_handler import register_esp_handler\nexcept ImportError:\n    print("esp_handler skipped - paho missing")\n    register_esp_handler = lambda bot: None/' handlers/loader.py

# 4. קומפילציה
python3 -m py_compile handlers/loader.py && echo "✅ loader OK"

# 5. commit + push (אם יש שינויים)
if ! git diff --quiet; then
    git add -A
    git commit -m "Termux fix: paho/groq install, BOM, loader guard"
    git push origin main
    echo "✅ Git pushed"
else
    echo "✅ No changes to push"
fi

# 6. הפעלת autopilot (אם קיים)
if [ -f slh_autopilot.py ]; then
    python3 slh_autopilot.py --fix
fi

# 7. הפעלה מחדש
pkill -f bot_stable.py 2>/dev/null
nohup python3 bot_stable.py > bot.log 2>&1 &
sleep 3
pgrep -f bot_stable.py && echo "✅ Bot running" || echo "⚠️ Bot not running – check bot.log"

echo "🔧 SLH FIX & PUSH – done"
echo "👉 Now send /logo or /ask in Telegram"
