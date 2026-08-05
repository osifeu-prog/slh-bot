#!/bin/bash
echo "=== מריץ SLH BOT מלא ==="

pkill -f gunicorn
pkill -f python
pkill -f node

echo "1. מריץ שרת API"
gunicorn webapp:app --bind 0.0.0.0:8080 --workers 2 > flask.log 2>&1 &

echo "2. מריץ בוט טלגרם"
python3 -u -B bot_stable.py > bot.log 2>&1 &

echo "3. מריץ בוט וואטסאפ"
node whatsapp_bot.js > whatsapp.log 2>&1 &

echo "✅ הכל עלה! בדוק logs עם: tail -f flask.log"
