#!/data/data/com.termux/files/usr/bin/bash
echo "🔍 FULL SYNC CHECK — $(date)"
cd ~/slh_clean
echo ">>> Git remote:" && git remote -v
echo ">>> Fetching remote..." && git fetch origin
LOCAL=$(git rev-parse main)
REMOTE=$(git rev-parse origin/main)
echo "Local HEAD:  ${LOCAL:0:7}"
echo "Remote HEAD: ${REMOTE:0:7}"
if [ "$LOCAL" = "$REMOTE" ]; then
    echo "✅ Local and remote are in sync"
else
    echo "❌ Local is ahead of remote (or diverged)"
fi
echo ">>> Unpushed commits:" && git log origin/main..HEAD --oneline
echo ">>> Local changes:" && git status --short
echo ">>> Testing push..." && git push --dry-run 2>&1
echo ">>> Bot key features:"
if grep -q "SLH_LOCAL" bot.py; then echo "✅ SLH_LOCAL guard present"; else echo "❌ Guard missing"; fi
if grep -q "commands=\['sync'\]" bot.py; then echo "✅ /sync exists"; else echo "❌ /sync missing"; fi
if grep -q "commands=\['id'\]" bot.py; then echo "✅ /id exists"; else echo "❌ /id missing"; fi
if grep -q "commands=\['request'\]" bot.py; then echo "✅ /request exists"; else echo "❌ /request missing"; fi
if grep -q "commands=\['vbackup'\]" bot.py; then echo "✅ /vbackup exists"; else echo "❌ /vbackup missing"; fi
if grep -q "commands=\['fullcheck'\]" bot.py; then echo "✅ /fullcheck exists"; else echo "❌ /fullcheck missing"; fi
echo ">>> Railway deployment status:"
if command -v railway &>/dev/null; then railway status 2>&1 || echo "Railway status command failed"; else echo "Railway CLI not installed (check Dashboard manually)"; fi
echo "✅ Full sync check completed"
