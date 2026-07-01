#!/data/data/com.termux/files/usr/bin/bash
set -e
cd ~/slh_clean

echo "🔐 עדכון BOT_TOKEN"
echo "הדבק את הטוקן החדש ולחץ Enter (הקלט לא יוצג על המסך):"
read -s NEW_TOKEN
echo ""

if [ -z "$NEW_TOKEN" ]; then
    echo "❌ לא הוזן טוקן, מבטל."
    exit 1
fi

# גיבוי config.json הנוכחי לפני שינוי
cp config.json "config.json.bak_$(date +%Y%m%d_%H%M%S)"

# עדכון הטוקן בקובץ באמצעות python (כדי לא לחשוף אותו כפרמטר שורת פקודה)
python3 << PYEOF
import json
with open("config.json") as f:
    cfg = json.load(f)
cfg["BOT_TOKEN"] = "$NEW_TOKEN"
with open("config.json", "w") as f:
    json.dump(cfg, f, indent=2, ensure_ascii=False)
PYEOF

echo "✅ config.json עודכן (גיבוי נשמר)"
echo ""
echo "--- אימות (רק prefix, לא הטוקן המלא) ---"
python3 -c "
import json
t = json.load(open('config.json'))['BOT_TOKEN']
print('אורך:', len(t), '| מתחיל ב:', t[:10])
"
echo ""
echo "⚠️  זכור: עדכן גם את Railway → Environment Variables → BOT_TOKEN"
