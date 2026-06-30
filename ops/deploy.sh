#!/data/data/com.termux/files/usr/bin/bash

cd ~/slh_clean || exit 1

echo "🧬 SLH SAFE DEPLOY"

# 1. pre-check
./pre_change_check.sh || exit 1

# 2. snapshot before change
./ops/snapshot.sh

# 3. restart bot
pkill -f bot_stable.py
sleep 2
./start.sh

echo "🚀 DEPLOY COMPLETE"
