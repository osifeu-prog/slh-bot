#!/bin/bash
# SLH Dashboard – colorful control panel

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color
BOLD='\033[1m'

clear
echo -e "${CYAN}${BOLD}"
echo "   ███████╗██╗     ██╗  ██╗"
echo "   ██╔════╝██║     ██║  ██║"
echo "   ███████╗██║     ███████║"
echo "   ╚════██║██║     ██╔══██║"
echo "   ███████║███████╗██║  ██║"
echo "   ╚══════╝╚══════╝╚═╝  ╚═╝"
echo -e "${NC}"
echo -e "${MAGENTA}      SLH Learning System Dashboard${NC}"
echo -e "${YELLOW}=======================================${NC}"

if pgrep -f "python.*bot.py" > /dev/null; then
    echo -e "🤖 Bot:        ${GREEN}● Running${NC}"
else
    echo -e "🤖 Bot:        ${RED}● Stopped${NC}"
    echo -e "   Starting bot..."
    ./slh_daemon.sh > /dev/null 2>&1
    sleep 3
fi

for f in bot.py learn_handlers.py project_commands.py smart_leaderboard.py; do
    if [ -f "$f" ]; then
        echo -e "📄 $f: ${GREEN}✓${NC}"
    else
        echo -e "📄 $f: ${RED}✗${NC}"
    fi
done

python3 << 'PYSTATS' 2>/dev/null
import json
try:
    db = json.load(open("db.json"))
    users = len(db.get("users", {}))
    students = len(db.get("students", {}))
    courses = len(db.get("courses", {}))
    commissions = db.get("commissions", {})
    total_comm = sum(commissions.values())
    token = "Yes" if db.get("token") else "No"
    print(f"👥 Users:      \033[1;32m{users}\033[0m")
    print(f"🎓 Students:   \033[1;32m{students}\033[0m")
    print(f"📚 Courses:    \033[1;32m{courses}\033[0m")
    print(f"💰 Commissions:\033[1;33m{total_comm} USDT\033[0m")
    print(f"🔑 Token:      \033[1;32m{token}\033[0m")
except Exception as e:
    print(f"\033[1;31mDB Error: {e}\033[0m")
PYSTATS

echo -e "${YELLOW}=======================================${NC}"
echo ""
echo -e "${BOLD}מה תרצה לעשות?${NC}"
echo "  1) 📢 שידור הודעה לכל המשתמשים"
echo "  2) 📊 הצג לוח מובילים (API)"
echo "  3) 🔄 הפעל מחדש את הבוט"
echo "  4) 🧪 בדיקת מערכת מלאה"
echo "  5) יציאה"
echo ""
read -p "בחירתך (1-5): " choice

case $choice in
    1)
        echo -e "${CYAN}📢 מריץ שידור...${NC}"
        python3 << 'BROADCAST'
import json, requests, time
with open("db.json") as f:
    db = json.load(f)
token = db.get("token") or __import__("os").environ.get("BOT_TOKEN")
if not token:
    print("❌ No token found"); exit(1)
users = db.get("users", {})
msg = """🌟 **SLH Learning – הבוט שודרג!** 🌟

🎯 שלחו /start כדי לראות את האפשרויות החדשות:
• /join – הרשמה
• /courses – קורסים
• /project create – פרויקטים
• /leaderboard – לוח מובילים
• /referral – הזמינו חברים והרוויחו!

👥 **בואו נבנה יחד!**"""
for uid in users:
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                         json={"chat_id": int(uid), "text": msg, "parse_mode": "Markdown"})
        print(f"{'✅' if r.status_code==200 else '❌'} {uid}")
        time.sleep(0.05)
    except Exception as e:
        print(f"❌ {uid}: {e}")
print("✅ שידור הסתיים")
BROADCAST
        ;;
    2)
        echo -e "${CYAN}📊 מושך נתוני Leaderboard...${NC}"
        python3 -c "
import json, requests
db = json.load(open('db.json'))
token = db.get('token') or __import__('os').environ.get('BOT_TOKEN')
if not token:
    print('No token found in db.json or BOT_TOKEN env var')
    exit(1)
r = requests.post(f'https://api.telegram.org/bot{token}/sendMessage',
                  json={'chat_id': 8789977826, 'text': '/leaderboard'})
print(r.json().get('result', {}).get('text', 'No response'))
"
        ;;
    3)
        echo -e "${CYAN}🔄 מפעיל מחדש...${NC}"
        pkill -9 -f "python.*bot.py"
        sleep 2
        ./slh_daemon.sh
        ;;
    4)
        echo -e "${CYAN}🧪 מריץ אבחון מלא...${NC}"
        python3 << 'CHECK'
import os, json, py_compile, datetime
issues = []
for fname, desc in [("bot.py","bot.py"),("learn_handlers.py","learn"),("project_commands.py","project"),("smart_leaderboard.py","smart")]:
    if os.path.exists(fname):
        try:
            py_compile.compile(fname, doraise=True)
            issues.append(f"✅ {desc} OK")
        except py_compile.PyCompileError as e:
            issues.append(f"❌ {desc} syntax: {e}")
    else:
        issues.append(f"❌ {desc} missing")
try:
    db = json.load(open("db.json"))
    required = ["users","students","courses","progress","admins","token","referral_codes","commissions","premium","votes","lost_reports"]
    missing = [k for k in required if k not in db]
    if missing:
        issues.append(f"⚠️ DB missing keys: {missing}")
    else:
        issues.append("✅ DB structure OK")
    if not db.get("token"):
        issues.append("❌ Token missing")
except Exception as e:
    issues.append(f"❌ DB corrupt: {e}")
print("\n".join(issues))
CHECK
        ;;
    5)
        echo "להתראות!"
        exit 0
        ;;
    *)
        echo "בחירה לא חוקית"
        ;;
esac
