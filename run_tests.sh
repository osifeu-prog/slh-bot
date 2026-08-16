#!/bin/bash
cd ~/slh_clean
echo "=============================================="
echo " SLH AUTOMATED TEST SUITE"
echo " $(date '+%Y-%m-%d %H:%M:%S')"
echo "=============================================="

ERRORS=0

# 1. Syntax check
echo ""
echo "📝 Syntax check..."
for f in handlers/loader.py bot_stable.py state/custom_handlers/*.py handlers/*.py; do
    if [ -f "$f" ]; then
        if python3 -m py_compile "$f" 2>/dev/null; then
            echo "  ✅ $f"
        else
            echo "  ❌ $f"
            ERRORS=$((ERRORS+1))
        fi
    fi
done

# 2. Hebrew spelling check
echo ""
echo "🔤 Hebrew spelling check..."
python3 << 'HEBCHECK'
import os, re
hebrew_pattern = re.compile(r'[\u0590-\u05FF]')
errors = 0
for root, dirs, files in os.walk("."):
    for f in files:
        if f.endswith(".py") and "archive" not in root:
            path = os.path.join(root, f)
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    for i, line in enumerate(fh, 1):
                        # Check for mixed RTL/LTR issues
                        if hebrew_pattern.search(line) and not line.strip().startswith("#"):
                            # Very basic: flag lines with both Hebrew and common English keywords
                            if re.search(r'\b(def|class|import|return|print|if|else|try|except)\b', line):
                                print(f"  ⚠️ Mixed Hebrew/English in {path}:{i}")
                                errors += 1
            except:
                pass
if errors == 0:
    print("  ✅ No issues found")
else:
    print(f"  ⚠️ {errors} potential issues")
HEBCHECK

# 3. JSON integrity
echo ""
echo "💾 JSON integrity..."
for f in state/db.json state/users.json state/tasks.json state/chats.json state/commands_registry.json config.json; do
    if python3 -c "import json; json.load(open('$f'))" 2>/dev/null; then
        echo "  ✅ $f"
    else
        echo "  ❌ $f"
        ERRORS=$((ERRORS+1))
    fi
done

# 4. Bot process
echo ""
echo "🤖 Bot process..."
if pgrep -af bot_stable.py > /dev/null; then
    echo "  ✅ Bot running"
else
    echo "  ⚠️ Bot not running"
fi

echo ""
echo "=============================================="
if [ $ERRORS -eq 0 ]; then
    echo " ✅ ALL TESTS PASSED"
else
    echo " ❌ $ERRORS ERROR(S) FOUND"
fi
echo "=============================================="
