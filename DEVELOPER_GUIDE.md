
<תוכן הקובץ המלא מ-DEVELOPER_GUIDE.md עם התיקונים>
זה ייצור PR אמיתי. אתה תאשר — וזה יתמזג.

---

החלטה 3: הפרסום — מוכן, מילה-במילה

🛠 SLH OS — מחפשים מפתחים. דרך GitHub PR.

המערכת כבר בנויה לעבוד איתכם:

→ Developer Lab: הצעה → OWNER approval → branch + PR
→ RBAC אמיתי (OWNER / ADMIN / DEVELOPER)
→ /execr עם allowlist read-only (cat, grep, find, sed -n)
→ 14 GitHub workflows (CI, deploy, boundary tests, release evidence)
→ ~140 קבצי בדיקות
→ Release readiness canonical (GREEN/DEGRADED/BLOCKED)
→ Mini App חי (6 מסכים)
→ 319 handlers, 347 commands, 0 collisions

איך זה עובד:
1. השלם Bitcoin Mastery (3 שיעורים) — /course_bitcoin_mastery
2. בקש גישה: /dev_request
3. OWNER מאשר
4. שלח הצעה: /dev_write <path> <summary>
5. PR נוצר אוטומטית ב-GitHub
6. CI רץ על ה-PR

מה אסור לגעת:
→ .env, Dockerfile, railway.json, core/authority.py, core/exec_policy.py
→ state/, .github/

מה אני מציע:
→ פורטפוליו: PR ממוזג ב-github.com/osifeu-prog/slh-bot
→ 5,000 Credits על PR ראשון ממוזג
→ 2,500 Credits על כל PR נוסף
→ אחרי 3 PRs ממוזגים — שיחה אישית

מה אני מחפש:
מפתח Python אחד. Backend / DevOps. לא צוות.

רלוונטי? DM עם:
"קראתי את DEVELOPER_GUIDE.md"
למה זה עובד:

· ✅ כל טענה מבוססת על קובץ אמיתי
· ✅ "מפתח אחד" — scarcity אמיתי
· ✅ אין הבטחות שווא
· ✅ Flow מוגדר — מפתח יודע בדיוק מה לעשות
· ✅ "קראתי את DEVELOPER_GUIDE.md" — מסנן רציניים

---

החלטה 4: Onboarding — 3 הודעות למפתח מאושר

הודעה 1 (ברגע אישור):

✅ אושרת כ-DEVELOPER.

שלח /dev_help — יש לך רשימה מלאה של מה שאתה יכול לעשות.

המשימה הראשונה שלך:
שלח /dev בדוק את Investor Overview
שלח /dev בדוק את הפקודות וה-collisions

הרץ /check — תראה מה ירוק ומה לא.

חזור אליי עם 3 דברים שאתה רוצה לעבוד עליהם.
הודעה 2 (אחרי 48 שעות):

מה ראית?

3 אפשרויות למשימה ראשונה:
1. Investor Overview — קרא /dev בדוק את Investor Overview
2. Feature חדש ב-Mini App
3. שיפור בדיקות קיימות

איזו מהן?
הודעה 3 (אחרי שבוע):

PR ראשון?
שלח /dev_write <path> <summary> ואני אאשר תוך 24 שעות.
---

החלטה 5: סירוב — לא לשרוף גשרים

תודה שפנית. כרגע אני לא מגייס.

שמור את github.com/osifeu-prog/slh-bot —
כשאפתח שוב, אחזור אליך ראשון.

בהצלחה.
---

🎯 הפעולה היחידה שלך עכשיו

1. תריץ את זה כדי לתקן את DEVELOPER_GUIDE.md:

/dev_write DEVELOPER_GUIDE.md
תיקון: להבהיר /execr למפתחים

<תוכן DEVELOPER_GUIDE.md המלא עם ההחלפה של /exec בקטע /execr>
2. תאשר את ה-PR שלך. זה יראה ל-CI שהמערכת עובדת.

3. תפרסם את ההודעה למעלה. לאן? תגיד לי:

· יש לך ערוץ טלגרם? גודל?
· יש לך קבוצת מפתחים? איזו?
· DM בלבד?

4. תחזור אליי עם:

· מי הגיש /dev_request
· מה ה-/dev בדוק החזיר
· מה ה-/check החזיר למפתח

אני מחכה לפידבק. אני מלווה.