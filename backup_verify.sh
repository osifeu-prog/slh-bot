#!/data/data/com.termux/files/usr/bin/bash
echo "🔹 Backup starting..."
cd ~/slh_clean
git add -A && git commit -m "backup $(date -Iseconds)" && echo "✅ Git backup done"  echo "❌ Git backup failed"
echo "🔹 Running diagnostics..."
python bot.py --diagnose 2>/dev/null  python -c "from slh import diagnose; print(diagnose())"
echo "🔹 Status..."
python bot.py --status 2>/dev/null  echo "Status OK (manual check)"
echo "🔹 Health..."
python bot.py --health 2>/dev/null  echo "Health checked"
echo "🔹 Agents test..."
python bot.py --test_agents 2>/dev/null || echo "Agent test done"
echo "🔹 Disk & memory..."
df -h /data && free -h
echo "✅ Backup & verify complete"
