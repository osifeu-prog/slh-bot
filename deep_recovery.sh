#!/data/data/com.termux/files/usr/bin/bash
echo "🔍 DEEP RECOVERY & DIAGNOSTIC — $(date)"
cd ~/slh_clean

# 1. Stop any running bot safely
echo ">>> Stopping any running bot..."
pkill -9 -f "python.*bot.py" 2>/dev/null
sleep 2

# 2. Restore stable version (commit 44e39b8 – Option B, all features working)
echo ">>> Restoring stable bot.py..."
git checkout 44e39b8 -- bot.py
echo "✅ bot.py restored to stable version"

# 3. Remove any leftover broken diag_handler and restore from git
echo ">>> Restoring diag_handler.py..."
git checkout 44e39b8 -- diag_handler.py 2>/dev/null  echo "diag_handler.py not in that commit, using current"
# Clean the warning line if present
sed -i '/handlers after while True/d' diag_handler.py

# 4. Verify syntax
echo ">>> Syntax check..."
python -c "import py_compile; py_compile.compile('bot.py', doraise=True)" && echo "✅ bot.py syntax OK"  echo "❌ Syntax error in bot.py"

# 5. Restart the bot
echo ">>> Starting bot..."
./slh_daemon.sh
sleep 5

# 6. Verify process
echo ">>> Bot process check..."
pgrep -af "python.*bot.py" && echo "✅ Bot is running"  echo "❌ Bot failed to start"

# 7. Run Python-based diagnostics (without Telegram dependency)
echo ">>> Core imports check..."
python -c "import slh; print('✅ slh importable')"  echo "❌ slh import failed"
python -c "import health_check; print('✅ health_check importable')"  echo "❌ health_check import failed"
python -c "import diag_handler; print('✅ diag_handler importable')"  echo "❌ diag_handler import failed"

# 8. Check health directly
echo ">>> Health check..."
python -c "import health_check" 2>&1 | head -20

# 9. Check agents test directly (if test_agents.py exists)
if [ -f "test_agents.json" ]; then
    echo ">>> Agents test file exists"
else
    echo "⚠️ test_agents.json missing"
fi

# 10. Git status
echo ">>> Git status..."
git status --short

echo "✅ Deep recovery completed. Now send /id from Telegram to confirm bot is alive."
