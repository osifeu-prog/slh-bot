# SLH OS — CURRENT STATE (מקור אמת)
עודכן: 2026-09-26 · כל PR שמשנה את אחד הסעיפים כאן חייב לעדכן את הקובץ הזה.

## Runtime
- **Production:** Railway project `slh-cloud-bot` · service `slh-cloud-bot` · `python3 -u -B bot_gateway.py`
- **Repo:** `osifeu-prog/slh-bot@main` · 1 replica · Volume `/app/state` (מקור ה-state היחיד)
- **Mini App:** `https://slh-cloud-bot-production.up.railway.app/mini-app-v4` (Menu Button הוגדר 2026-09-26)
- **Bot:** `@Me_ad_main_bot` — polling רק ב-`slh-cloud-bot`
- **slh-api:** פרויקט נפרד עם Postgres (ledger נפרד)
- **LEGACY:** `endearing-amazement/web` (`web-production-22f28`) — `RUN_BOT=0`, Volume ישן ונפרד. לא production. עדיין מגיש את `/api/ai/chat` לווידג'ט ה-AI של האתר.
- **PC agent:** `PC_Osif2` — heartbeat דרך MQTT, supervisor ב-Task Scheduler

## כללי עבודה (חובה לכל סוכן)
1. כל שינוי קוד — PR ל-`main`. `/e` לקריאה בלבד: שינוי קבצים בקונטיינר נמחק בדיפלוי הבא.
2. אין כתיבה ישירה ל-`state/db.json`. רק דרך השירותים (atomic_update).
3. תיקון אחד לכל PR. CI חייב לעבור לפני דיפלוי.
4. פלט אמיתי מהשרת = רק תשובה ל-`/e`. תשובות AI על קוד אינן ראיה.
5. לא לסמן LIVE / מאומת בלי ראיה מה-runtime.

## כסף
- **TON:** פתוח (`TON_DEPOSITS_OPEN=1`). קופה ב-`ton_settings.wallet`. שער 100 Credits/TON, מוגן בטווח 100–110. זיכוי רק אחרי TON Proof binding + sender/recipient/memo `SLH<uid>`.
- **BNB / SLH Live:** שער `BNB_DEPOSITS_OPEN` (כרגע `1` לפי החלטת הבעלים). קופת BSC `0x693d…1f02` מואצלת (EIP-7702) לחוזה שמעביר כל BNB נכנס ל-`0xd0a1…e3a9` — לבדוק לפני הפקדות לקוחות. `CREDITS_PER_BNB=1000` קבוע בקוד (לא תואם מחיר שוק).
- **Stars:** 100⭐️ = 100 Credits (`core/stars_price_authority.py`).

## פתוח
ראה `docs/EXECUTOR_BRIEF_2026-09-26.md`.
