#!/data/data/com.termux/files/usr/bin/bash

set -u

ROOT="$HOME/slh_clean"
cd "$ROOT" || exit 1

REPORT="state/reports"
mkdir -p "$REPORT"

STAMP=$(date +%Y%m%d_%H%M%S)
LOG="$REPORT/full_audit_$STAMP.log"

PASS=0
WARN=0
FAIL=0

pass(){
echo "PASS | $1"
PASS=$((PASS+1))
}

warn(){
echo "WARN | $1"
WARN=$((WARN+1))
}

fail(){
echo "FAIL | $1"
FAIL=$((FAIL+1))
}

exec > >(tee "$LOG") 2>&1

echo
echo "========================================="
echo " SLH FULL DOCTOR"
echo "========================================="
echo

echo "TIME:"
date

echo
echo "ROOT:"
pwd

echo
echo "========================================="
echo "01 SYSTEM"
echo "========================================="

python3 --version && pass "Python"
git --version && pass "Git"

echo
df -h .

echo
echo "========================================="
echo "02 GIT"
echo "========================================="

git rev-parse --short HEAD
git branch --show-current
git status --short
git remote -v

echo
echo "========================================="
echo "03 UPDATE"
echo "========================================="

pkg update -y || warn "pkg update"
pkg upgrade -y || warn "pkg upgrade"

python3 -m pip install --upgrade pip setuptools wheel

[ -f requirements.txt ] && \
python3 -m pip install -r requirements.txt || warn "requirements"

echo
echo "========================================="
echo "04 FILES"
echo "========================================="

FILES="
bot_stable.py
requirements.txt
handlers/loader.py
handlers/advanced_ask_handler.py
handlers/llm_handler.py
handlers/logo_handler.py
handlers/esp_handler.py
core/system_collector.py
core/identity.py
state/db.json
state/agents.json
"

for f in $FILES
do
    if [ -f "$f" ]
    then
        pass "$f"
    else
        fail "$f missing"
    fi
done

echo
echo "========================================="
echo "05 JSON"
echo "========================================="

python3 <<'PY'
import json,glob

files=glob.glob("state/*.json")

for f in files:
    try:
        json.load(open(f,encoding="utf-8"))
        print("PASS",f)
    except Exception as e:
        print("FAIL",f,e)
PY

echo
echo "========================================="
echo "06 COMPILE"
echo "========================================="

python3 -m compileall -q .

if [ $? -eq 0 ]
then
pass "Compile"
else
fail "Compile"
fi

echo
echo "========================================="
echo "07 IMPORTS"
echo "========================================="

python3 <<'PY'
import importlib

mods=[
"handlers.loader",
"handlers.advanced_ask_handler",
"handlers.llm_handler",
"handlers.logo_handler",
"handlers.esp_handler",
"core.identity",
"core.system_collector"
]

for m in mods:
    try:
        importlib.import_module(m)
        print("PASS",m)
    except Exception as e:
        print("FAIL",m,e)
PY

echo
echo "========================================="
echo "08 PACKAGES"
echo "========================================="

python3 <<'PY'
import importlib

pkgs=[
"telebot",
"requests",
"groq",
"paho.mqtt.client",
"dotenv"
]

for p in pkgs:
    try:
        importlib.import_module(p)
        print("PASS",p)
    except Exception as e:
        print("FAIL",p,e)
PY

echo
echo "========================================="
echo "09 ENV"
echo "========================================="

env | grep -Ei 'BOT|TOKEN|GROQ|GEMINI|RAILWAY' | sed 's/=.*$/=********/'

echo
echo "========================================="
echo "10 HANDLERS"
echo "========================================="

python3 <<'PY'
import telebot
from handlers.loader import load_handlers

bot=telebot.TeleBot("123:test")


try:
    load_handlers(bot,None)
    print("PASS loader")
except Exception as e:
    print("FAIL loader",e)

cmds=[]

for h in getattr(bot,"message_handlers",[]):
    cmds.extend(h.get("filters",{}).get("commands",[]))

cmds=sorted(set(cmds))

print()
print("Commands:")
for c in cmds:
    print("/",c)

print()

mandatory=[
"start",
"help",
"ask",
"admin",
"status"
]

for c in mandatory:
    if c in cmds:
        print("PASS",c)
    else:
        print("FAIL",c)
PY

echo
echo "========================================="
echo "11 PYTEST"
echo "========================================="

python3 -m pytest -q || warn "pytest"

echo
echo "========================================="
echo "12 PROCESS"
echo "========================================="

pgrep -af bot_stable.py

echo
echo "========================================="
echo "13 RESTART"
echo "========================================="

pkill -f bot_stable.py

sleep 2

nohup python3 -u -B bot_stable.py > bot.log 2>&1 &

sleep 5

pgrep -af bot_stable.py

echo
echo "========================================="
echo "14 LOG"
echo "========================================="

tail -50 bot.log

echo
echo "========================================="
echo "15 DISK"
echo "========================================="

df -h .

echo
echo "========================================="
echo "16 SUMMARY"
echo "========================================="

echo
echo "PASS : $PASS"
echo "WARN : $WARN"
echo "FAIL : $FAIL"
echo
echo "Report:"
echo "$LOG"
echo

