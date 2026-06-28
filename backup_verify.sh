#!/data/data/com.termux/files/usr/bin/bash
set -e
echo "🔹 Backup & Verify started at $(date)"
cd ~/slh_clean

# 1. Git backup
echo ">>> Git backup..."
if git add -A && git commit -m "backup $(date -Iseconds)"; then
    echo "✅ Git backup done"
else
    echo "❌ Git backup failed"
fi

# 2. Diagnostics (using slh or diag_handler)
echo ">>> Diagnostics..."
if python -c "from diag_handler import diagnose; print(diagnose())" 2>/dev/null; then
    :
else
    echo "⚠️ diagnose via diag_handler failed, trying slh..."
    python -c "from slh import diagnose; print(diagnose())" 2>/dev/null  echo "❌ Diagnostics unavailable"
fi

# 3. Status / health / agents via simple checks
echo ">>> Status..."
python -c "from slh import get_status; print(get_status())" 2>/dev/null  echo "Status not available"

echo ">>> Health..."
python -c "from health_check import check; print(check())" 2>/dev/null  echo "Health check not available"

echo ">>> Agent self-test..."
python -c "from test_agents import run_test; print(run_test())" 2>/dev/null  echo "Agent test not available"

# 4. Disk & memory
echo ">>> Disk & Memory..."
df -h /data 2>/dev/null || df -h /
free -h

echo "✅ Backup & Verify completed at $(date)"
