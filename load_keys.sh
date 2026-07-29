#!/bin/bash
source ~/slh-bot/keys.secure
cd ~/slh-bot
cat > config.json << EOF
{
  "BOT_TOKEN": "8737037440:AAEJU4jK-UpuiAHHNz4RNobahi3rTUllDy0",
  "OWNER_ID": "8789977826",
  "OPENAI_API_KEY": "$OPENAI_API_KEY",
  "BINANCE_API_KEY": "$BINANCE_API_KEY",
  "BINANCE_SECRET": "$BINANCE_SECRET",
  "DB_PATH": "state/db.json",
  "DEMO_MODE": false
}
EOF
pkill -f bot_stable.py && sleep 1
nohup python3 bot_stable.py > bot.log 2>&1 &
sleep 2
echo "✅ בוט הודלק עם מפתחות מ-keys.secure"
echo "DEMO_MODE:" && grep "DEMO_MODE" config.json
