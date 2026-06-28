#!/data/data/com.termux/files/usr/bin/bash
echo "🔹 Backup & Verify started at $(date)"
cd ~/slh_clean

# 1. Git backup
echo ">>> Git backup..."
if git add -A && git commit -m "backup $(date -Iseconds)"; then
    echo "✅ Git backup done"
else
    echo "❌ Git backup failed"
fi

# 2. Bot running?
echo ">>> Bot process..."
if pgrep -f "python.*bot.py" > /dev/null; then
    echo "✅ Bot is running"
else
    echo "❌ Bot NOT running"
fi

# 3. Core modules import check (no argument functions)
echo ">>> Core imports..."
if python -c "import slh" 2>/dev/null; then
    echo "✅ slh imported successfully"
else
    echo "❌ slh import failed"
fi

# 4. Critical files existence
echo ">>> Critical files..."
for f in bot.py db.json events.db config.json; do
    if [ -f "$f" ]; then
        echo "  ✅ $f exists"
    else
        echo "  ❌ $f MISSING"
    fi
done

# 5. Disk & memory
echo ">>> Disk & Memory..."
df -h /data 2>/dev/null  df -h /
free -h

echo "✅ Backup & Verify completed at $(date)"
echo "ℹ️ For full system diagnostic run /diagnose via Telegram"
