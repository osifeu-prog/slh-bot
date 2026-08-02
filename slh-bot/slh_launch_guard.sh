#!/data/data/com.termux/files/usr/bin/bash

set -e

echo "======================================"
echo " 🚀 SLH LAUNCH GUARD"
echo " $(date)"
echo "======================================"

echo
echo "1) Cleaning stale runtime..."

rm -f runtime/bot.pid


echo
echo "2) Checking token..."

python3 - <<'PY'
import json,urllib.request,sys

token=json.load(open("config.json"))["BOT_TOKEN"]

r=urllib.request.urlopen(
f"https://api.telegram.org/bot{token}/getMe",
timeout=5
).read().decode()

if '"ok":true' not in r:
    sys.exit(1)

print("✅ Telegram token OK")
PY


echo
echo "3) Checking webhook..."

python3 - <<'PY'
import json,urllib.request

token=json.load(open("config.json"))["BOT_TOKEN"]

r=urllib.request.urlopen(
f"https://api.telegram.org/bot{token}/getWebhookInfo",
timeout=5
).read().decode()

print(r)

if '"url":""' not in r:
    print("⚠️ webhook exists")
PY


echo
echo "4) Lock state"

if [ -f .bot.lock ]; then
 echo "⚠️ lock exists:"
 cat .bot.lock
else
 echo "✅ no lock"
fi


echo
echo "5) Snapshot"

if [ -x stable_checkpoint_20260712.sh ]; then
 ./stable_checkpoint_20260712.sh || true
else
 echo "snapshot script missing"
fi


echo
echo "6) Railway"

railway status


echo
echo "======================================"
echo " ✅ SLH READY FOR LAUNCH"
echo "======================================"
