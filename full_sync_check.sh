#!/data/data/com.termux/files/usr/bin/bash
echo "🔍 FULL SYNC CHECK — $(date)"
cd ~/slh_clean

# 1. Check git remote
echo ">>> Git remote:"
git remote -v

# 2. Check local vs remote
echo ">>> Fetching remote..."
git fetch origin
LOCAL=$(git rev-parse main)
REMOTE=$(git rev-parse origin/main)
echo "Local HEAD:  ${LOCAL:0:7}"
echo "Remote HEAD: ${REMOTE:0:7}"
if [ "$LOCAL" = "$REMOTE" ]; then
    echo "✅ Local and remote are in sync"
else
    echo "❌ Local is ahead of remote (or diverged)"
fi

# 3. Check unpushed commits
echo ">>> Unpushed commits:"
git log origin/main..HEAD --oneline

# 4. Check untracked/uncommitted changes
echo ">>> Local changes:"
git status --short

# 5. Check if push works
echo ">>> Testing push..."
git push --dry-run 2>&1

# 6. Check if bot.py has the guard and recent functions
echo ">>> Bot key features:"
grep -q "SLH_LOCAL" bot.py && echo "✅ SLH_LOCAL guard present"  echo "❌ Guard missing"
grep -q "commands=['sync']" bot.py && echo "✅ /sync exists"  echo "❌ /sync missing"
grep -q "commands=['id']" bot.py && echo "✅ /id exists"  echo "❌ /id missing"
grep -q "commands=['request']" bot.py && echo "✅ /request exists"  echo "❌ /request missing"
grep -q "commands=['vbackup']" bot.py && echo "✅ /vbackup exists"  echo "❌ /vbackup missing"

# 7. Railway deployment log (last 10 lines from web.log if available)
echo ">>> Railway last deploy log (from web.log):"
tail -n 10 web.log 2>/dev/null  echo "No web.log"

echo "✅ Full sync check completed"
