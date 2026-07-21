# SLH OS – Operations Manual

## 1. פתיחת יום
1. שלח /start לטלגרם – וודא שהברכה "רובוטוש" מופיעה.
2. שלח /status – וודא Users > 0, Agents > 0.
3. שלח /health – וודא RAM, Disk, DB תקינים.
4. שלח /morning_report – תמונת מצב מלאה.

## 2. סגירת יום
1. בטלגרם: /backup (גיבוי Git).
2. ב‑Termux: הפעל את בלוק "End of Day Closure".
3. בטלגרם: /status – וודא שהכל תקין.

## 3. גיבוי ושחזור
- גיבוי אוטומטי: /backup שומר ל‑Git.
- גיבוי ידני: cp state/*.json backups/eod_$(date +%Y%m%d_%H%M)/
- שחזור: cp backups/<תיקייה>/db.json state/ ואז railway up.

## 4. ניקוי מערכת
- הסרת סוכנים לא נחוצים: /agentstate <name> retired
- הסרת משתמשי דמו: דרך /exec (לפי צורך)
- ניקוי לוגים: /clean

## 5. חירום
- הבוט לא מגיב: railway service restart web
- Railway down: railway up
- Git corrupted: git reset --hard origin/main

## 6. מכשיר מזוהה
- Admin Device: PLACEHOLDER_DEVICE_ID (יש להזין ידנית)
