#!/data/data/com.termux/files/usr/bin/bash
echo "🔍 FULL SYNC CHECK — $(date)"
cd ~/slh_clean
echo ">>> Git remote:" && git remote -v
echo ">>> Fetching remote..." && git fetch origin
LOCAL=$(git rev-parse main)
REMOTE=$(git rev-parse origin/main)
echo "Local HEAD:  ${LOCAL:0:7}"
echo "Remote HEAD: ${REMOTE:0:7}"
[ "$LOCAL" = "$REMOTE" ] && echo "✅ Local and remote are in sync"  echo "❌ Local is ahead of remote (or diverged)"
echo ">>> Unpushed commits:" && git log origin/main..HEAD --oneline
echo ">>> Local changes:" && git status --short
echo ">>> Testing push..." && git push --dry-run 2>&1
echo ">>> Bot key features:"
grep -q "SLH_LOCAL" bot.py && echo "✅ SLH_LOCAL guard present"  echo "❌ Guard missing"
grep -q "commands=\['sync'\]" bot.py && echo "✅ /sync exists"  echo "❌ /sync missing"
grep -q "commands=\['id'\]" bot.py && echo "✅ /id exists"  echo "❌ /id missing"
grep -q "commands=\['request'\]" bot.py && echo "✅ /request exists"  echo "❌ /request missing"
grep -q "commands=\['vbackup'\]" bot.py && echo "✅ /vbackup exists"  echo "❌ /vbackup missing"
grep -q "commands=\['fullcheck'\]" bot.py && echo "✅ /fullcheck exists"  echo "❌ /fullcheck missing"
echo ">>> Railway deployment status:"
command -v railway &>/dev/null && railway status 2>&1  echo "Railway CLI not installed (check Dashboard manually)"
echo "✅ Full sync check completed"
