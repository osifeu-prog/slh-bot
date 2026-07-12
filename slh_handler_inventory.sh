#!/data/data/com.termux/files/usr/bin/bash

echo "=========================================="
echo " SLH HANDLER INVENTORY"
echo "$(date)"
echo "=========================================="

echo
echo "=== HANDLER FILES ==="

find . -maxdepth 2 -name "*handler*.py" -o -name "*handlers*.py" | sort


echo
echo "=== BOT COMMAND REGISTRY ==="

grep -R "@bot.message_handler(commands" -n . \
--exclude-dir=.git \
--exclude="*.pyc" \
2>/dev/null | sort


echo
echo "=== INIT / REGISTER LOADERS ==="

grep -R "init(bot\|register_" -n bot_stable.py \
--exclude="*.pyc" \
2>/dev/null


echo
echo "=== STARTUP LOADING LOGIC ==="

grep -n "loaded\|Loading\|HANDLER\|MODULE" bot_stable.py | tail -100


echo
echo "=== PYTHON IMPORT HEALTH ==="

python3 - <<'PY'
import os, ast

bad=[]

for f in os.listdir("."):
    if f.endswith(".py"):
        try:
            ast.parse(open(f,encoding="utf-8").read())
        except Exception as e:
            bad.append((f,str(e)))

if bad:
    print("❌ Syntax problems:")
    for x in bad:
        print(x)
else:
    print("✅ Python files syntax OK")
PY


echo
echo "=== CURRENT BOT COMMANDS IN CORE ==="

grep -R "commands=\[" -n . \
--exclude-dir=.git \
--exclude="*.pyc" \
2>/dev/null | wc -l


echo
echo "=========================================="
echo " INVENTORY COMPLETE"
echo "=========================================="
