# SLH Bot — מקור אמת יחיד
עודכן: 2026-06-30

## הקובץ הפעיל
**bot_stable.py** — רץ גם בטרמוקס וגם ב-Railway (Procfile, railway.json, Dockerfile מצביעים אליו).
bot.py הוא ארכיון בלבד — לא להריץ, לא לערוך.

## Handlers פעילים
- welcome_handler.init(bot)
- course_handlers.register_course_handlers(bot)
- learn_handlers.register(bot)
- project_commands.register(bot)
- smart_leaderboard.register(bot)
- logger_handler — מושבת בכוונה (# disabled)

## כללי ברזל
1. רק שרת אחד מותר polling בו-זמנית (Railway או טרמוקס, לא שניהם)
2. לפני כל שינוי: ./pre_change_check.sh + ./ops/snapshot.sh
3. אחרי כל שינוי: בדיקת syntax + git commit + git push
4. לא לבנות handler חדש בלי לבדוק חתימת פונקציה קיימת קודם

## עדכון 2026-06-30 (אחה"צ)
✅ Railway = production יחיד, מאומת (פקודות /admin, /termux, /debug עובדות מהטלגרם)
✅ תוקן: nested quotes ב-f-string (Python 3.11 incompatibility) ששבר build
✅ Railway CLI מותקן ומחובר בטרמוקס (railway logs/status זמינים)
✅ טרמוקס נעול מהרצה מקומית - dev-only מעכשיו
🔜 הבא בתור: בדיקת המנועים הגדולים (SLH_KERNEL, master_agent) וחיבורם
