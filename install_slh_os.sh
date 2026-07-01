#!/data/data/com.termux/files/usr/bin/bash

echo "════════════════════════════════════════════"
echo "  SLH OS v2.0 – One-Click Installer"
echo "════════════════════════════════════════════"
echo ""

# 1. תיקיות בסיס
mkdir -p ~/slh_os_installed
cd ~/slh_os_installed

# 2. העתקת קבצי הליבה (אם קיימים)
if [ -d ~/slh_clean ]; then
    cp -r ~/slh_clean/core ./
    cp -r ~/slh_clean/plugins ./
    cp -r ~/slh_clean/web ./
    cp ~/slh_clean/bot_stable.py ./
    cp ~/slh_clean/audit_logger.py ./
    cp ~/slh_clean/config.json ./
    cp ~/slh_clean/requirements.txt ./
    cp ~/slh_clean/Dockerfile ./
    cp ~/slh_clean/Procfile ./
    cp ~/slh_clean/plugins_store.py ./
    cp ~/slh_clean/watchdog.sh ./
    echo "✅ Core files copied"
else
    echo "❌ ~/slh_clean not found – clone from GitHub:"
    echo "   git clone https://github.com/osifeu-prog/slh-bot.git ~/slh_clean"
    exit 1
fi

# 3. התקנת תלויות
pip install flask flask-cors pyTelegramBotAPI --break-system-packages 2>/dev/null
echo "✅ Dependencies installed"

# 4. הפעלת שירותים
pkill -f "python3.*bot_stable.py" 2>/dev/null
pkill -f "web/api/app.py" 2>/dev/null
pkill -f "http.server 8000" 2>/dev/null

nohup python3 -B bot_stable.py >> bot.log 2>&1 &
nohup python3 web/api/app.py >> web.log 2>&1 &
nohup python3 -m http.server 8000 -d web/dashboard >> /dev/null 2>&1 &

sleep 2

echo ""
echo "════════════════════════════════════════════"
echo "  ✅ SLH OS INSTALLED SUCCESSFULLY"
echo "════════════════════════════════════════════"
echo ""
echo "  Bot:     @Me_ad_main_bot"
echo "  API:     http://localhost:5000/api/health"
echo "  Dashboard: http://localhost:8000"
echo ""
echo "  Run again:  cd ~/slh_os_installed && ./watchdog.sh"
echo "════════════════════════════════════════════"
