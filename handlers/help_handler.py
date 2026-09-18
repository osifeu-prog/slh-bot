def register(bot):
    @bot.message_handler(commands=['help'])
    def help_cmd(msg):
        text = """📘 SLH OS — מפת המערכת

🏠 ACCOUNT
/start – בית / התחלה
/join – הרשמה
/me – פרופיל קצר
/profile – פרופיל וארנק

🛍 MARKET & PRODUCTS
/shop – קטלוג מוצרים
/buy <item_id> – רכישה ב-Credits
/buystars <item_id> – רכישת מוצר ב-Telegram Stars
/pay – רכישת Credits ב-Telegram Stars
/history – היסטוריית עסקאות
/paysupport – תמיכה בתשלום

👛 WALLET & MONEY
/wallet – ארנק מלא
/balance – יתרת Credits
/transfer <uid> <amount> – העברת Credits
/p2p_slh <uid> <amount> – העברת SLH
/stake <amount> – Staking ל-30 יום
/stake_lock <amount> <days> – Staking לתקופה
/positions – פוזיציות
/unstake <position_id> – שחרור
/rewards – תגמולים
/ton – סטטוס TON
/claim – Claim BNB

🎮 EXPERIENCE
/arcade – משחק
/arcade_stop – עצירת משחק
/top – טבלת מובילים

🎓 ACADEMY
/academy – Academy
/courses – קורסים
/course_bitcoin_mastery – Bitcoin Mastery
/lesson – שיעור
/finish – סיום שיעור
/progress – התקדמות
/map – מפת למידה

🤖 AGENTS
/agents – סוכנים
/agent_create <name> – יצירת סוכן
/agent_delete <id> – מחיקה
/agentstate <prefix> <state> – מצב סוכן
/sendagent <prefix> <msg> – שליחה לסוכן
/inbox <prefix> – תיבת סוכן

🎯 MISSIONS & GOVERNANCE
/task – משימות
/task_add – הוספת משימה
/mission – משימות/מיסיות
/complete – השלמת משימה
/vote <id> <yes/no> – הצבעה
/propose <text> – הצעה
/tally <id> – תוצאות
/gov_status – סטטוס Governance

🎁 SHARE & REFERRAL
/share – קישור הזמנה וסטטוס
/refer – קיצור ל-Share
/invite – קיצור ל-Share

🔗 LEGACY WALLET
/migrate <legacy_bnb_wallet> – חיבור ארנק ישן
/migrate_verify <wallet> <signature> – אימות בעלות

🛠 TOOLS
/miniapp – Mini App
/dashboard – Dashboard
/status – סטטוס
/health – בדיקת בריאות
/doctor – אבחון
/megadiag – אבחון מלא
/ask <question> – AI

🔐 ADMIN
/admin – Control Center
/exec <cmd> – ביצוע פקודה
/execr – בקשת ביצוע
/autoexec – אוטומציה
/backup – גיבוי
/logs – לוגים
/deploy – Deploy

💡 טיפ: לממשק מלא פתח /miniapp. הפקודות נשארות זמינות למשתמשים מתקדמים ולאוטומציה."""
        bot.reply_to(msg, text)
