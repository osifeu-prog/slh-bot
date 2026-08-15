# SLH Bot — Session Status (2026-08-15)

## תוקן היום
- קידוד mojibake ב-admin_extras.py (4 שורות אימוג'ים)
- מיזוג economy-core-freeze branch ל-main, ללא איבוד עבודה
- 14 command handlers שהיו רשומים בקוד אך לא נטענים בפועל
  (roadmap, doctor, tutorial, guide, language, ועוד) — עכשיו פעילים
- admin_menu.sh שוחזר מארכיון (slh-bot-broken)
- לוגו Termux תוקן והועבר לריפו (assets/termux_logo.txt)

## ידוע ופתוח
- Staking: קיים גם ב-handlers/staking_handler.py (חי) וגם בארכיון
  web3_disabled — צריך אימות איזה גרסה רצה בפועל בפרודקשן
- כלכלה: קרדיטים נכנסים כרגע רק דרך /giveme (admin) ו-/fakepay (test) —
  אין עדיין חיבור תשלום אמיתי (Stars/TON)
- קיימת תשתית ESP (handlers/esp_handler.py) טעונה ופעילה — לא נבדקה לעומק
- דשבורד web (dashboard-v2) קיים בהיסטוריה, לא אומת שהוא חי כרגע

## Production
- Railway: web service, branch main, commit מסונכרן
- URL: web-production-22f28.up.railway.app

## להרצה ראשונה (מפתח חדש)
./setup_dev_env.sh && source ~/.bashrc
