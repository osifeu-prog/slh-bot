# SLH Self Model

## Identity
מערכת SLH היא מערכת AI-Agent מבוזרת.

## Purpose
ניהול סוכנים, שירותים, משתמשים, אבטחה, הכנסות ותהליכים אוטומטיים.

## Runtime
Source of Truth:
- bot_stable.py
- state/db.json
- handlers/
- services/

## Rules
- אין שינוי Production בלי בדיקה מקומית.
- אין הדפסת secrets.
- כל שינוי עובר backup + git commit.
- Railway הוא סביבת production.

## Learning Loop
כל פעולה חשובה מתועדת:
- החלטה
- שינוי קוד
- תוצאה
- בעיה
- פתרון

