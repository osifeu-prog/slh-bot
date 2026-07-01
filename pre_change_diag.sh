#!/data/data/com.termux/files/usr/bin/bash
echo "════════════════════════════════════════"
echo " SLH — בדיקת מצב לפני הרצת slh_daemon.sh"
echo "════════════════════════════════════════"

echo ""
echo "--- 1. Railway production (בדיקה מרוחקת) ---"
curl -s -m 8 -o /tmp/railway_check.txt -w "HTTP Status: %{http_code}\n" \
  https://web-production-22f28.up.railway.app/ 2>/dev/null || echo "❌ לא הצליח להתחבר ל-Railway"
echo "תוכן תשובה (אם יש):"
cat /tmp/railway_check.txt 2>/dev/null
echo ""

echo "--- 2. תהליכי בוט מקומיים (טרמוקס) ---"
ps aux | grep -i "bot" | grep -v grep || echo "אין תהליכי בוט רצים מקומית"
echo ""

echo "--- 3. Ollama ---"
pgrep -f ollama > /dev/null && echo "✅ Ollama רץ" || echo "❌ Ollama לא רץ"
ollama list 2>/dev/null || echo "לא ניתן לקבל רשימת מודלים"
echo ""

echo "--- 4. דיסק ---"
df -h /data 2>/dev/null | grep -v "com.google.android.gms"
echo ""

echo "--- 5. Cron jobs פעילים ---"
crontab -l 2>/dev/null || echo "אין cron jobs"
echo ""

echo "--- 6. שינויים לא-committed ב-git ---"
cd ~/slh_clean
git status --short 2>/dev/null || echo "לא ניתן לבדוק git status"
echo ""

echo "--- 7. הטוקן זהה בכל מקום? ---"
python3 -c "
try:
    from get_token import get_token
    print('טוקן מקומי (4 תווים ראשונים):', get_token()[:4] + '...')
except Exception as e:
    print('שגיאה בקריאת טוקן:', e)
" 2>/dev/null
echo ""

echo "--- 8. אימות תחביר bot_stable.py ---"
python3 -c "import py_compile; py_compile.compile('bot_stable.py', doraise=True); print('✅ תחביר תקין')" 2>&1
echo ""

echo "════════════════════════════════════════"
echo " סיום בדיקה"
echo "════════════════════════════════════════"
