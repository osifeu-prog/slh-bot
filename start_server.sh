#!/bin/bash
echo "=== SLH SERVER START ===" >> server.log
date >> server.log

gunicorn webapp:app --bind 0.0.0.0:8080 --workers 2 >> server.log 2>&1 &
python bot.py >> server.log 2>&1 &
node whatsapp_bot.js >> server.log 2>&1 &

echo "כל הלוגים ב: server.log" 
tail -f server.log
