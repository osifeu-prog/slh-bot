#!/bin/bash
echo "=== SLH BOT FULL START ==="
termux-wake-lock

gunicorn webapp:app --bind 0.0.0.0:8080 --workers 2 > flask.log 2>&1 &
python bot.py > bot.log 2>&1 &
node whatsapp_bot.js > whatsapp.log 2>&1 &
sleep 3

echo "4. פותח לעולם עם Cloudflare..."
echo "מחכה 10 שניות ללינק..."
cloudflared tunnel --url http://localhost:8080 2>&1 | tee tunnel.log &
CF_PID=$!

sleep 10
TUNNEL=$(grep -o 'https://.*trycloudflare.com' tunnel.log | head -1)

if [ -z "$TUNNEL" ]; then
  echo "❌ לא מצא לינק. תעתיק ידנית מ tunnel.log"
  cat tunnel.log
else
  echo "======================"
  echo "✅ הכל עלה!"
  echo "לינק לחנות: $TUNNEL/market"
  echo "שלח לקבוצה: $TUNNEL/market"
  echo "======================"
  echo $TUNNEL > current_url.txt
fi
