#!/bin/bash
cd ~/slh-bot
cat ~/.termux_logo.txt
echo ""
echo "🌿 branch: $(git branch --show-current)"
echo "📦 git:    $(git status --short | wc -l) שינויים לא-committed"
echo "🚀 last:   $(git log -1 --oneline)"
echo "🩺 syntax: $(python3 -m py_compile bot_gateway.py 2>&1 && echo '✅ OK' || echo '❌ FAIL')"
echo ""
echo "פקודות זמינות: gs (status) | gp (push) | rl (railway logs) | rs (railway status) | aud (audit)"
