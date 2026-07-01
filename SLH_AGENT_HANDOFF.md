עדכון 1 ביולי 2026 - Token Security and Bot Duplication Fix

מצב production נוכחי:
Railway (endearing-amazement, web-production-22f28.up.railway.app) הוא ה-production היחיד.
טרמוקס משמש לפיתוח ודיבוג בלבד, לא אמור להריץ בוט במקביל.
/health עובד משני הצדדים, Railway מציג Uptime, RAM, Disk מלאים.

מה נפתר היום:

1. טוקן דלף הוחלף.
הטוקן הישן נחשף בטעות בפלט דיאגנוסטיקה, get_token.py הדפיס secrets אגב import.
טוקן חדש הופק ב-BotFather, מעודכן ב-config.json המקומי וב-Railway Environment Variables.
get_token.py תוקן, הפך לפונקציה get_token שמחזירה ערך רק כשנקראת.

2. בעיית 409 Conflict, בוט כפול, שורש הבעיה.
slh_daemon.sh ו-watchdog.sh הריצו את bot.py הישן והשבור, לא bot_stable.py.
3 סקריפטים תוקנו: slh_daemon.sh, install_slh_os.sh חלקית, watchdog.sh.
bot.py הישן לא נמחק, נשאר קוד מת בכוונה.

3. תכונה חדשה: /refreshtoken
קובץ חדש refresh_token_handler.py, רשום ב-bot_stable.py.
זרימה: פקודה, אישור, שליחת טוקן חדש, מחיקה מיידית של ההודעה, אימות מול Telegram getMe, שמירה עם גיבוי אוטומטי.
בכוונה לא מבצע עדכון Railway אוטומטי, נשאר ידני משיקולי אבטחה.
is_admin מיובא מ-bot_stable עצמו בתוך init, לא מודול נפרד.

4. תשתית.
llama3.2:1b הוסר מ-Ollama, שוחררו 1.3GB.
psutil נוסף ל-requirements.txt.

פתוח לסשן הבא:
1. ניקוי git, יש קבצי בק לא committed.
2. סקריפטי דיאגנוסטיקה ישנים עדיין בודקים bot.py הישן.
3. install_slh_os.sh שורה 17 עדיין מעתיק bot.py.
4. החלטה פתוחה, אוטומציית Railway מלאה ל-refreshtoken.
5. לבדוק תלות ב-bot.py לפני מחיקה סופית.
6. שילוב עם מערכת היומן האישי, ראה סעיף למטה.

כללי אבטחה שחוזקו היום:
אין להדפיס טוקנים מלאים בפלט, רק prefix לאימות.
railway variables בלי json מציג ערכים מלאים, להשתמש ב-railway variables עם דגל json.
מנגנון רענון טוקן מוחק הודעות עם secrets מיידית.
