#!/data/data/com.termux/files/usr/bin/bash

echo "===== SLH SNAPSHOT ====="

echo "[SYSTEM STATUS]"
ps aux | grep python | grep -v grep

echo ""
echo "[FILES]"
ls -la

echo ""
echo "[CONFIG]"
cat system_profile.json

echo ""
echo "[GIT STATUS]"
git status 2>/dev/null || echo "No git repo"

echo "===== END SNAPSHOT ====="
