#!/data/data/com.termux/files/usr/bin/bash

echo "=========================================="
echo " SLH BROADCAST READINESS CHECK"
echo " $(date)"
echo "=========================================="

echo
echo "=== SYSTEM FILES ==="
for f in \
bot_stable.py \
slh_daemon.sh \
slh_lock.py \
config.json \
token_sync.sh \
update_token.sh \
runtime/bot.pid \
.env
do
    if [ -e "$f" ]; then
        echo "✅ $f"
    else
        echo "❌ MISSING $f"
    fi
done


echo
echo "=== PYTHON SYNTAX CHECK ==="
python3 -m py_compile bot_stable.py
if [ $? -eq 0 ]; then
 echo "✅ bot_stable.py syntax OK"
else
 echo "❌ Syntax problem"
fi


echo
echo "=== TOKEN HEALTH ==="
python3 - <<'PY'
import json,urllib.request

try:
    token=json.load(open("config.json"))["BOT_TOKEN"]
    r=urllib.request.urlopen(
        f"https://api.telegram.org/bot{token}/getMe",
        timeout=5
    ).read().decode()

    print(r)

except Exception as e:
    print("TOKEN FAILURE:",e)
PY


echo
echo "=== TELEGRAM POLLING STATE ==="

python3 - <<'PY'
import json,urllib.request

token=json.load(open("config.json"))["BOT_TOKEN"]

for x in ["getWebhookInfo","getUpdates"]:
    print("\n"+x)
    try:
        print(
        urllib.request.urlopen(
        f"https://api.telegram.org/bot{token}/{x}",
        timeout=5
        ).read().decode()
        )
    except Exception as e:
        print(e)
PY


echo
echo "=== LOCAL PROCESS GUARD ==="

ps aux | grep -E "bot_stable.py|slh_daemon|python3" | grep -v grep || true


echo
echo "=== LOCK STATUS ==="

if [ -f .bot.lock ]; then
    echo "⚠️ LOCK EXISTS"
    cat .bot.lock
else
    echo "✅ NO ACTIVE LOCK"
fi


echo
echo "=== RAILWAY STATUS ==="

railway status


echo
echo "=== LAST RAILWAY EVENTS ==="

railway logs --tail 60 | \
grep -E "LOCK|POLLING|ERROR|Conflict|RUNNING|handler loaded" \
|| true


echo
echo "=== BROADCAST ASSETS ==="

for f in \
broadcast_handler.py \
welcome_handler.py \
branding \
marketplace.json \
ROADMAP.md \
STATUS.md
do
 if [ -e "$f" ]; then
    echo "✅ $f"
 else
    echo "❌ $f"
 fi
done


echo
echo "=========================================="
echo " READY CHECK COMPLETE"
echo "=========================================="
