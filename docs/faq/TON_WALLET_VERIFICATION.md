# FAQ — אימות ארנק TON (binding)

## למה צריך אימות?

הפקדת TON לאוצר **לא מזהה לבד** מי המשתמש בטלגרם.

| שרשרת | SLH |
|--------|-----|
| TON הגיע ל-Treasury | נראה on-chain |
| מי הבעלים בבוט? | רק אחרי binding |
| זיכוי Credits | רק אחרי binding + בדיקת TX |

אימות = **TON Connect + ton_proof** — הוכחה שאתה שולט בכתובת, בלי לשלוח מפתח פרטי.

## מה זה לא?

- שליחת TON בלבד
- TX hash / צילום מסך בלבד
- **@wallet** בטלגרם (custodial — אין חתימה)
- יצירת ארנק חדש עם 12 מילים (זה ארנק אחר)
- הזנת seed ב-Mini App — **אסור ולא נתמך**

## ארנקים נתמכים

- MyTonWallet, Tonkeeper, TON Space (non-custodial)
- **לא** @wallet

## איך מאמתים (משתמש)

1. פתח Mini App **מתוך Telegram**
2. ארנק → «אמת ארנק TON»
3. בחר MyTonWallet / Tonkeeper
4. אשר **Connect** ואז **Proof** (לעיתים שתי בקשות) — תוך דקות
5. סטטוס: מאומת + כתובת מקוצרת

## אחרי אימות — הפקדה

1. שער הפקדות פתוח (המערכת)
2. שליחה לכתובת האוצר עם **Memo אישי** `SLH<uid>`
3. **מאותו ארנק שאומת**
4. בדיקת זיכוי Credits לפי השער

## שגיאות נפוצות

| קוד / מצב | מה לעשות |
|-----------|----------|
| מחובר, ממתין ל-Proof | אשר חתימה בארנק, לא רק Connect |
| TON_CHALLENGE_EXPIRED | לחץ אימות שוב ואשר מיד |
| Proof נדחה | קרא את הקוד; נסה שוב מתוך Telegram |
| @wallet בלבד | עבור ל-Tonkeeper / MyTonWallet |

## KYC

**אימות ארנק ≠ KYC.**  
KYC הוא זיהוי זהות רגולטורי (אם יופעל בעתיד). FAQ זה מכסה רק binding טכני.

## מפעיל — אבחון

```text
# Challenge לפי uid; bindings לפי address (לא לפי uid כמפתח)
get_ton_binding("UID")
# או לולאה על ton_wallet_bindings.values() לפי uid
```
