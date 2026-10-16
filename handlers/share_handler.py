"""Share & Referral handler."""
import state_manager
from core import referral_reward


def register(bot):
    @bot.message_handler(commands=["share", "refer", "invite"])
    def share_cmd(msg):
        uid = str(msg.from_user.id)

        db = state_manager.load_db()
        users = db.get("users", {})
        u = users.get(uid, {})

        try:
            bot_username = getattr(bot.get_me(), "username", None)
        except Exception:
            bot_username = None
        if not bot_username:
            bot_username = "Me_ad_main_bot"
        bot_username = str(bot_username).lstrip("@").strip()

        link = f"https://t.me/{bot_username}?start=ref_{uid}"

        ref = referral_reward.progress(uid)
        count = int(ref.get("count", 0) or 0)
        required = int(ref.get("required", 5) or 5)
        remaining = int(ref.get("remaining", max(0, required - count)) or 0)
        per = ref.get("per_successful_referral", {}) if isinstance(ref.get("per_successful_referral"), dict) else {}
        commission = db.get("commissions", {}).get(uid, 0)

        text = (
            "🎁 הזמנה ו-Referral\n\n"
            f"🔗 {link}\n\n"
            f"👥 משתמשים שהוזמנו בהצלחה: {count}\n"
            f"🎁 על כל הצטרפות מוצלחת: +{per.get('credits', 0)} Credits +{per.get('points', 0)} Points\n"
            f"⭐ אחרי {required} referrals: חודש VIP (הצעת השקה) · עוד {remaining}\n\n"
            f"💰 עמלת רכישות שהצטברה: {commission}\n\n"
            "התגמול ניתן על הצטרפות מוצלחת, לא על עצם הלחיצה/השיתוף."
        )
        try:
            from core.trader_certification import referral_course_promo_status
            promo = referral_course_promo_status(uid, db)
            if promo.get("awarded"):
                text += (
                    "\\n\\n✅ הטבת קורס המסחר שלך אושרה — מקום "
                    f"{promo.get('slot')}/15. פתח /courses כדי להתחיל."
                )
            elif promo.get("remaining", 0) > 0:
                text += (
                    "\\n\\n🎓 הטבת השקה: קורס המסחר בחינם ל־15 מפנים ראשונים. "
                    "כדי להבטיח זכאות, משתתף חדש צריך להיכנס דרך הקישור האישי "
                    "ולהשלים הרשמה מוצלחת. שיתוף או לחיצה בלבד אינם ניתנים לאימות. "
                    f"מקומות שנותרו: {promo.get('remaining')}/15."
                )
            else:
                text += "\\n\\nℹ️ הטבת 15 קורסי המסחר החינמיים הסתיימה."
        except Exception:
            text += "\\n\\nℹ️ מצב הטבת קורס המסחר אינו זמין כרגע; אין להניח שהמקום נשמר."
        bot.reply_to(msg, text)
