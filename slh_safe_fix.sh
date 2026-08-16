#!/data/data/com.termux/files/usr/bin/bash
set -u

echo "🛡  SLH SAFE DIAGNOSTICS & FIX"
echo "==============================="

# ---------- 1. תיקון תלויות בסיסיות ----------
echo "📦 מתקין תלויות חסרות…"
pkg update -y > /dev/null 2>&1  true
pkg install -y python-psutil > /dev/null 2>&1  true

pip install --upgrade pip setuptools wheel > /dev/null 2>&1  true
pip install groq paho-mqtt python-dotenv requests > /dev/null 2>&1  true

# ---------- 2. תיקון קובץ JSON פגום (BOM) ----------
python3 << 'PYFIX'
import pathlib
p = pathlib.Path("state/monitor_config.json")
if p.exists():
    try:
        data = p.read_bytes()
        if data.startswith(b'\xef\xbb\xbf'):
            p.write_text(data.decode('utf-8-sig'), encoding='utf-8')
            print("✅ BOM הוסר מ-monitor_config.json")
        else:
            print("✅ monitor_config.json תקין (אין BOM)")
    except Exception as e:
        print("⚠️  שגיאה בטיפול ב-monitor_config.json:", e)
PYFIX

# ---------- 3. הגנה על ה-loader מפני חוסר paho ----------
echo "🔒 מוודא שהבוט לא ייפול בגלל ESP…"
python3 << 'PYFIX'
loader = "handlers/loader.py"
with open(loader, 'r', encoding='utf-8') as f:
    content = f.read()

# החלפת ה-import הרגיל ב-try/except
old = "from handlers.esp_handler import register_esp_handler"
new = '''try:
    from handlers.esp_handler import register_esp_handler
except ImportError:
    print("⚠️  ESP handler skipped – paho-mqtt missing")
    register_esp_handler = lambda bot: None'''

if old in content and "except ImportError" not in content:
    content = content.replace(old, new)
    with open(loader, 'w', encoding='utf-8') as f:
        f.write(content)
    print("✅ Loader מוגן – ESP לא יפיל את הבוט")
else:
    print("✅ Loader כבר מוגן (או שאין צורך)")
PYFIX

# ---------- 4. התקנת שאר החבילות מתוך requirements.txt ----------
if [ -f requirements.txt ]; then
    pip install -r requirements.txt > /dev/null 2>&1  echo "⚠️  חלק מהחבילות מ-requirements.txt לא הותקנו (אך קריטיות כבר קיימות)"
fi

# ---------- 5. קומפילציה ויבוא ----------
echo "🔍 בודק תקינות קוד…"
python3 -m compileall -q . 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✅ כל קבצי Python תקינים"
else
    echo "❌ נמצאו שגיאות תחביר – בדוק ידנית"
fi

echo "🔍 בודק ייבואים קריטיים…"
python3 << 'PYTEST'
import sys, importlib

mods = [
    "handlers.loader",
    "handlers.advanced_ask_handler",
    "handlers.llm_handler",
    "core.identity",
    "core.system_collector"
]
failed = False
for m in mods:
    try:
        importlib.import_module(m)
        print("PASS:", m)
    except Exception as e:
        print("FAIL:", m, str(e))
        failed = True
if failed:
    sys.exit(1)
print("✅ כל הייבואים הקריטיים עובדים")
PYTEST

# ---------- 6. בדיקת LLM אמיתי ----------
echo "🧠 בודק חיבור LLM…"
python3 << 'PYTEST'
from handlers.llm_handler import query_llm_with_context
answer = query_llm_with_context("מה השעה?", "8789977826")
print("LLM REPLY:", answer[:150])
PYTEST

# ---------- 7. אתחול מחדש של הבוט (אם היה רץ) ----------
echo "🔄 מפעיל מחדש את הבוט…"
pkill -f bot_stable.py 2>/dev/null  true
sleep 2
nohup python3 -u -B bot_stable.py > bot.log 2>&1 &
echo $! > .bot.lock
sleep 4
if pgrep -f bot_stable.py > /dev/null; then
    echo "✅ בוט רץ!"
else
    echo "❌ הבוט לא עלה – בדוק bot.log"
fi

echo "==============================="
echo "🎯 סיום. שלח /ask מה השעה? פעם אחת."
