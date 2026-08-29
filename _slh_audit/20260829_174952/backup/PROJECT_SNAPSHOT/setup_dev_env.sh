#!/bin/bash
set -e
echo "🚀 SLH Dev Environment Setup"

# 1. לוגו + locale
cp "$(pwd)/assets/termux_logo.txt" ~/.termux_logo.txt
if ! grep -q "termux_logo.txt" ~/.bashrc 2>/dev/null; then
cat >> ~/.bashrc << 'BASHEOF'

# === SLH Dev Environment ===
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8
cat ~/.termux_logo.txt
alias c='clear && bash ~/slh-bot/admin_menu.sh'
alias gs='git status --short'
alias gp='git add -A && git commit -m "update" && git push origin main'
alias rl='railway logs --service web --tail 50'
alias rs='railway status'
alias aud='python3 tools/project_audit.py'
BASHEOF
fi

echo "✅ לוגו, locale, וקיצורים הותקנו"
echo "✅ הרץ: source ~/.bashrc כדי להפעיל עכשיו"
echo ""
echo "📋 מבנה הפרויקט:"
echo "  - tools/project_audit.py    -> מיפוי פקודות/פיצ'רים אמיתי"
echo "  - handlers/loader.py        -> רשימת כל ה-handlers הטעונים"
echo "  - admin_menu.sh             -> דשבורד סטטוס (c)"
echo ""
echo "לתיעוד מלא: cat SESSION_STATUS.md"
