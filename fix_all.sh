#!/data/data/com.termux/files/usr/bin/bash
# שמירה בתור ~/slh_clean/fix_all.sh
set -e
cd ~/slh_clean

echo "🔁 משחזר את bot.py לגרסה היציבה האחרונה..."
git checkout 08fb76b -- bot.py

echo "🧹 מסיר handlers מיותרים שנמצאים אחרי while True (אם יש)..."
python3 << 'CLEANEOF'
import re
with open("bot.py", "r") as f:
    code = f.read()

loop = code.find("while True:")
if loop == -1:
    print("❌ לא נמצא while True – צא")
    exit(1)

after = code[loop:]
removed_any = False
for cmd in ["fix", "reload", "alert"]:
    pat = rf"(@bot\.message_handler\(commands=\['{cmd}'\]\).*?)(?=\n@bot|\nwhile True:|\n*$)"
    m = re.search(pat, after, re.DOTALL)
    if m:
        block = m.group(1)
        code = code.replace(block, "")
        print(f"✅ הוסר /{cmd} אחרי while True")
        removed_any = True

if not removed_any:
    print("ℹ️  לא נמצאו handlers מיותרים, הכל נקי")

code = code.rstrip() + "\n"
with open("bot.py", "w") as f:
    f.write(code)
CLEANEOF

echo "🔍 בודק תקינות תחביר..."
python3 -c "import py_compile; py_compile.compile('bot.py', doraise=True)" && echo "✅ תחביר תקין"

echo "🔄 מפעיל מחדש את הבוט..."
pkill -9 -f "python.*bot.py" 2>/dev/null || true
sleep 2
./slh_daemon.sh

echo ""
echo "✅ הכל תוקן והבוט רץ. שלח /diagnose בטלגרם כדי לוודא."
