#!/bin/bash
while true; do
  curl -s https://web-production-22f28.up.railway.app/api/health > /dev/null
  if [ $? -eq 0 ]; then echo "$(date) ✅ ONLINE"; else echo "$(date) ❌ DOWN"; fi
  sleep 60
done
