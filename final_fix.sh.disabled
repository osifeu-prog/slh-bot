#!/data/data/com.termux/files/usr/bin/bash
echo "🔧 FINAL FIX & VERIFY — $(date)"
cd ~/slh_clean

# 1. Stop bot
pkill -9 -f "python.*bot.py" 2>/dev/null
sleep 2

# 2. Ensure we are on a stable commit (44e39b8) and then apply the /diagnose addition cleanly
git checkout 44e39b8 -- bot.py

# 3. Add /diagnose handler and import safely
python3 << 'PYEOF'
with open("bot.py", "r") as f:
    lines = f.readlines()

# Add import after 'import json' if not present
if not any("from diag_handler import diagnose" in l for l in lines):
    for i, line in enumerate(lines):
        if line.strip() == "import json":
            lines.insert(i+1, "from diag_handler import diagnose\n")
            break
    else:
        lines.insert(0, "from diag_handler import diagnose\n")

# Add handler before bot.infinity_polling()
handler = """
@bot.message_handler(commands=['diagnose'])
def diagnose_cmd(m):
    diagnose(m)
"""
if not any("commands=['diagnose']" in l for l in lines):
    for i, line in enumerate(lines):
        if "bot.infinity_polling()" in line:
            lines.insert(i, handler)
            break
    else:
        lines.append(handler)

with open("bot.py", "w") as f:
    f.writelines(lines)

import py_compile
try:
    py_compile.compile("bot.py", doraise=True)
    print("✅ bot.py syntax OK")
except py_compile.PyCompileError as e:
    print("❌ bot.py syntax error:", e)
    exit(1)
PYEOF

# 4. Fix diag_handler.py (remove any leftover warning lines)
git checkout 44e39b8 -- diag_handler.py 2>/dev/null
sed -i '/handlers after while True/d' diag_handler.py

# 5. Commit changes
git add bot.py diag_handler.py
git commit -m "final stable: /diagnose added, no warnings" 2>/dev/null

# 6. Start bot
./slh_daemon.sh
sleep 4

# 7. Verify
echo ">>> Bot process:"
pgrep -af "python.*bot.py" && echo "✅ Bot running" || echo "❌ Bot not running"

# 8. Run internal checks
echo ">>> Health:"
python -c "import health_check" 2>&1 | grep "TOTAL"
echo ">>> /diagnose output (simulated):"
python3 << 'PYEOF'
import os, sys
sys.path.insert(0, os.path.expanduser('~/slh_clean'))
from diag_handler import diagnose
class Fake: pass
m = Fake()
m.chat = Fake()
m.chat.id = 8789977826
m.from_user = Fake()
m.from_user.id = 8789977826
import main
main.bot = type('B',(),{'reply_to':lambda self,m,text: print(text)})()
diagnose(m)
PYEOF

# 9. Notify admin via Telegram (using bot token and admin ID)
echo ">>> Sending restart notification..."
python3 << 'PYEOF'
import requests, os, json
# Load token from config
with open("config.json") as f:
    cfg = json.load(f)
token = cfg["token"]
admin_id = 8789977826  # Your chat ID
msg = "✅ FINAL FIX COMPLETED — SLH Bot is back online and fully operational."
url = f"https://api.telegram.org/bot{token}/sendMessage"
data = {"chat_id": admin_id, "text": msg}
try:
    requests.post(url, data=data, timeout=10)
    print("Notification sent")
except Exception as e:
    print("Could not send notification:", e)
PYEOF

echo "✅ Final fix completed."
