#!/data/data/com.termux/files/usr/bin/sh

DATE=$(date '+%Y-%m-%d %H:%M:%S')
OUT="state/SLH_STABLE_CHECKPOINT_20260712.md"

mkdir -p state

echo "# SLH Stable Checkpoint" > "$OUT"
echo "" >> "$OUT"
echo "Date: $DATE" >> "$OUT"
echo "" >> "$OUT"

echo "## Git State" >> "$OUT"
git status --short >> "$OUT" 2>&1

echo "" >> "$OUT"
echo "## Current Commit" >> "$OUT"
git rev-parse HEAD >> "$OUT"

echo "" >> "$OUT"
echo "## Tags" >> "$OUT"
git tag --points-at HEAD >> "$OUT"

echo "" >> "$OUT"
echo "## Railway Status" >> "$OUT"
railway status >> "$OUT" 2>&1

echo "" >> "$OUT"
echo "## Runtime Log" >> "$OUT"
railway logs --tail 50 >> "$OUT" 2>&1

echo "" >> "$OUT"
echo "## Telegram Check" >> "$OUT"

if [ -f config.json ]; then
TOKEN=$(grep -o '"BOT_TOKEN": *"[^"]*"' config.json | cut -d'"' -f4)
curl -s "https://api.telegram.org/bot$TOKEN/getUpdates?limit=1" >> "$OUT"
else
echo "config.json not found" >> "$OUT"
fi

echo ""
echo "✅ CHECKPOINT CREATED:"
echo "$OUT"

