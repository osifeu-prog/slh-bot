עדכון 21 ביולי 2026 - Rules-First Cleanup Session (Journal Split Fix + Dangerous Script Neutralization)

מצב production נוכחי:
Railway (endearing-amazement, web-production-22f28.up.railway.app) הוא ה-production היחיד, מאומת Online אחרי כל שינוי בסשן זה (railway status + railway logs נבדקו).
טרמוקס משמש לפיתוח ודיבוג בלבד.

מה נפתר היום:

1. תהליך preflight מלא בוצע לפני נגיעה בקוד.
נקראו AGENT_RULES.md, KERNEL_RULES.md, SYSTEM_RULES.md, SOURCE_OF_TRUTH.md, DO_NOT_RUN_LOCALLY.md, SLH_AGENT_HANDOFF.md (הגרסה הקודמת).
הורץ /journal_read בטלגרם בפועל (לא רק דיאגנוסטיקה מקומית) לפי כלל 9.
גילוי: journal.json חסר תיעוד לתקופה 15-21 ביולי (רק שורה ריקה "בדיקת SLH OS" ל-15-Jul), למרות עדויות בתיקיית backups/ לעבודה משמעותית שכן קרתה (pre_governance_phase, pre_phase95_governance, stable_2026_07_20, end_of_day_20260721_0016). מסקנה: מישהו לא תיעד ביומן בהתאם לכלל 9 באחד הסשנים האחרונים - יש להקפיד על כך קדימה.

2. bot.py - נבדק סופית ונסגר (היה סעיף פתוח מ-1-Jul).
אושר: bot.py כבר לא קיים בדיסק כלל. אין תלות ייבוא פעילה בנתיב החי. רק סקריפטי דיאגנוסטיקה ישנים עדיין מתייחסים אליו (ומדווחים כראוי "missing").

3. נוטרלו שני סקריפטים מסוכנים בפועל, לא רק מיושנים.
deep_recovery.sh ו-final_fix.sh (הועברו ל-.disabled) - שניהם עשו git checkout 44e39b8 -- bot.py (מחזירים לחיים קוד ארכיון מכוון) וגם הריצו ./slh_daemon.sh (מפעילים בוט מקומית בטרמוקס) - הפרה ישירה של DO_NOT_RUN_LOCALLY.md, סיכון ממשי ל-409 Conflict מהסוג שתועד ב-1-Jul. final_fix.sh גם עשה git commit אוטומטי והדליף טוקן דרך מפתח שגוי (config.json["token"] במקום BOT_TOKEN).

4. ניקוי git - הוסרו 5 קבצי scratch/כפילות שנכנסו בטעות ב-git add -A.
automation_handlers.txt, handler_audit_live.txt, scripts_dump.txt (קבצי dump זמניים מהסשן), core/ask_debug.py.bak.* ו-core/ask_guard.py.bak.* (אומתו כזהים ביטים לגרסה החיה לפני הסרה, via diff). נשמר RELEASE_STATUS_2026_07_21.md (תוכן אמיתי). נוסף *.txt ל-.gitignore.

5. install_slh_os.sh - נבדק, כבר לא קיים. סעיף סגור, לא נדרשה פעולה.

6. תוקן פיצול אמיתי במערכת היומן (handoff הקודם רמז לזה בלי לפרט - "ראה סעיף למטה" שמעולם לא נכתב).
handlers/llm_handler.py (get_bot_context + פקודת /journal_ask) קרא/כתב ל-state/journal.json, בעוד /journal ו-/journal_read (report_handler.py) עובדים מול journal.json בשורש - בדיוק אותה בעיית Volume/git split שסשן 4-Jul Part 7 חשב שפתר לגמרי, אך לא כיסה את llm_handler.py. אוחד לנתיב אחד (journal.json בשורש) ב-handlers/llm_handler.py וב-self_model_audit.py.
תוקן גם באג נלווה: /journal_ask השתמש ב-datetime.now() בלי import datetime (רק json,os יובאו) - גרם ל-NameError שקט בכל שמירה מוצלחת, נבלע ע"י except עירום.
אושר: from groq import Groq ברמת המודול (שורה 2 של llm_handler.py) הוא מקור אזהרת "No module named 'groq'" שנצפתה ב-bot.log בתחילת הסשן. לא טופל השבוע (מחוץ לתחום), נדרש pip install groq או תיקון requirements.txt.

7. תוקנה תקלת תשתית ב-Termux (לא בפרויקט עצמו, אך חוסמת עבודה).
~/.bashrc הכיל שתי שורות RAILWAY_TOKEN סותרות (אחת עם טוקן קבוע פג-תוקף, שנייה מצביעה ל-~/.railway/token שלא קיים) - גרם ל-railway login/logs/status להיכשל עם "Invalid RAILWAY_TOKEN" במקום לפתוח זרימת דפדפן. הוסרו שתי השורות אחרי אימות ש-railway CLI מאמת דרך ~/.railway/config.json (סשן OAuth), לא דרך משתנה הסביבה. אומת עם railway whoami אחרי הניקוי.

כל שינוי קוד עבר py_compile לפני commit. כל שלב בוצע כ-commit נפרד עם push מיידי (לא batch). Railway אומת Online + logs נקיים אחרי כל deploy.

פתוח לסשן הבא:
1. 4 סקריפטי דיאגנוסטיקה ישנים עדיין מתייחסים ל-bot.py שהוסר ולנתיבי db.json ישנים (לא בשורש state/): daily_check.sh, full_diagnostic.sh, full_sync_check.sh, backup_verify.sh. לא מסוכנים, רק לא מדויקים.
2. פאקג' groq עדיין לא מותקן ב-requirements.txt/deploy - /ask ותכונות LLM פועלות במצב מוגבל.
3. פער תיעוד ביומן ל-15-21 ביולי (ראה סעיף 1 למעלה) - להקפיד על משמעת תיעוד קדימה.
4. החלטה פתוחה: אוטומציית Railway מלאה ל-refreshtoken (שיקול עסקי/אבטחה, לא טכני).
5. קובץ גיבוי ~/.bashrc.before_railway_token_cleanup נשאר בדיסק להשוואה - בטוח למחיקה אחרי כמה ימי יציבות.

כללי אבטחה שחוזקו היום:
כל בדיקת env/טוקן הוצגה עם prefix בלבד (6-10 תווים), לא ערך מלא, גם בפקודות בדיקה.
כל שינוי אושר במפורש לפני כתיבה (git checkout/rm/sed), בהתאם לכלל 2.
