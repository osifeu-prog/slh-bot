#!/data/data/com.termux/files/usr/bin/bash

echo "==============================="
echo " SLH PRE BROADCAST AUDIT"
echo " $(date)"
echo "==============================="

echo
echo "===== 1. LOCAL PROCESSES ====="
ps aux | grep -E "bot_stable|slh_daemon|python3" | grep -v grep || true

echo
echo "===== 2. LOCK FILES ====="
ls -la .bot.lock runtime/ 2>/dev/null || true

echo
echo "===== 3. DAEMON ====="
ls -la slh_daemon.sh start*.sh watchdog*.sh 2>/dev/null

echo
echo "===== 4. TOKEN FILES ====="
ls -la config.json .env token_sync.sh update_token.sh 2>/dev/null || true

echo
echo "===== 5. TOKEN TEST ====="
python3 - <<'PY'
import json,urllib.request

try:
    token=json.load(open("config.json"))["BOT_TOKEN"]
    print("TOKEN EXISTS:", token[:10]+"...")
    print(
    urllib.request.urlopen(
    f"https://api.telegram.org/bot{token}/getMe",
    timeout=5
    ).read().decode()
    )
except Exception as e:
    print("TOKEN ERROR:",e)
PY

echo
echo "===== 6. TELEGRAM STATE ====="
python3 - <<'PY'
import json,urllib.request

token=json.load(open("config.json"))["BOT_TOKEN"]

for endpoint in ["getWebhookInfo","getUpdates"]:
    print("\n",endpoint)
    try:
        print(
        urllib.request.urlopen(
        f"https://api.telegram.org/bot{token}/{endpoint}",
        timeout=5
        ).read().decode()[:2000]
        )
    except Exception as e:
        print(e)
PY


echo
echo "===== 7. RAILWAY ====="
railway status

echo
echo "===== 8. RAILWAY LAST LOG ====="
railway logs --tail 40

echo
echo "===== 9. STARTUP FILES ====="
grep -R "polling\|restart\|lock\|BOT_TOKEN\|PID" \
bot_stable.py slh_daemon.sh slh_lock.py start*.sh 2>/dev/null | head -100

echo
echo "===== END AUDIT ====="
