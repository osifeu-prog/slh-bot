"""Share & Referral handler."""
import state_manager


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

        ref = u.get("referral", {}) if isinstance(u.get("referral"), dict) else {}
        count = ref.get("count", 0)
        commission = db.get("commissions", {}).get(uid, 0)

        text = (
            "🎁 הזמנה ו-Referral\n\n"
            f"🔗 {link}\n\n"
            f"👥 משתמשים שהוזמנו בהצלחה: {count}\n"
            "🎁 על כל הצטרפות מוצלחת: +0.9 Credits +10 Points\n"
            "⭐ אחרי 5 referrals: חודש VIP (הצעת השקה)\n\n"
            f"💰 עמלת רכישות שהצטברה: {commission}\n\n"
            "התגמול ניתן על הצטרפות מוצלחת, לא על עצם הלחיצה/השיתוף."
        )
        bot.reply_to(msg, text)
