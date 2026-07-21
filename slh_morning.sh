#!/bin/bash
echo "=== START DAY $(date) ==="
cd ~/slh_clean
git pull
railway status
echo "🟢 Ready to work."
