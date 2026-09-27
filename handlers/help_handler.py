def register(bot):
    @bot.message_handler(commands=["faq"])
    def faq_cmd(msg):
        try:
            from core.faq_service import telegram_faq
            bot.reply_to(msg, telegram_faq())
        except Exception:
            bot.reply_to(msg, "FAQ לא זמין כרגע.")

    @bot.message_handler(commands=["help"])
    def help_cmd(msg):
        text = """📘 SLH OS — מפת המערכת

🏠 ACCOUNT
/start – בית / התחלה
/join – הרשמה
/me – פרופיל קצר
/profile – פרופיל וארנק

🚀 TRADING TERMINAL
/trade – מסוף המסחר
/token <address> – סורק טוקן
/swap <chain> <address> – פתיחת מסחר
/portfolio – פורטפוליו
/trade_model – מודל הכנסות שקוף
/tradepro – Trade Pro

🛍 MARKET & PRODUCTS
/shop – קטלוג מוצרים
/buy <item_id> – רכישה ב-Credits
/buystars <item_id> – רכישת מוצר ב-Telegram Stars
/pay – רכישת Credits ב-Telegram Stars
/history – היסטוריית עסקאות
/paysupport – תמיכה בתשלום
/my_orders – הזמנות ותיקון אספקה ללא חיוב נוסף
/cardpay – סליקת כרטיסים למוצרים פיזיים שהוגדרו מראש
/card_orders – סטטוס/שחזור הזמנות כרטיס ללא חיוב נוסף

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

🔐 BOT VAULT (OWNER / PRIVATE CHAT)
/vault — רשימת בוטים ומטא־דאטה
/vault_verify [@bot] — אימות הצפנה + זהות Telegram
/vault_add <token> [module] — הוספה מוצפנת
/vault_rotate <@bot> <new_token> — סיבוב טוקן
/vault_remove <@bot> — הסרה
/vault_health [@bot] — health לכל בוט
/vault_exposed <@bot> <source> [note] — רישום חשיפה
/vault_log — audit אחרון
/vault_help — עזרה לכספת

📊 OWNER BUSINESS CONTROL
/biz – תמונת עסק כללית
/biz_users [days] – כניסות משתמשים
/biz_revenue [days] – הכנסות מאומתות
/biz_ai – מצב AI
/biz_bots – מלאי bots
/bots – מפת bots מאוחדת: Vault + Factory + Railway
/bot_seed – רישום הצהרות BotFather
/bot_register <@username> [name] – רישום בוט
/bot_status <@username> – תקינות בוט

🛠 TOOLS
/miniapp – Mini App
/dashboard – Dashboard
/status – סטטוס
/health – בדיקת בריאות
/doctor – אבחון
/megadiag – אבחון מלא
/ask <question> – AI
/faq – שאלות נפוצות

🔐 ADMIN
/admin – Control Center
/exec <cmd> – ביצוע פקודה
/execr – בקשת ביצוע
/autoexec – אוטומציה
/backup – גיבוי
/logs – לוגים
/deploy – Deploy

💡 לממשק המלא פתח /miniapp. למסחר: /trade."""
        bot.reply_to(msg, text)
