#!/data/data/com.termux/files/usr/bin/bash
cd ~/slh_clean
git pull origin main
git add -A
git commit -m "sync $(date)" 
git push
railway up
echo "✅ Synced to Railway"
