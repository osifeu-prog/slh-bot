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
        bot_username = bot_username or "Me_ad_main_bot"
        link = f"https://t.me/{bot_username}?start=ref_{uid}"

        ref = u.get("referral", {}) if isinstance(u.get("referral"), dict) else {}
        count = ref.get("count", 0)
        commission = db.get("commissions", {}).get(uid, 0)

        remaining = max(0, 5 - int(count or 0))
        milestone = (
            "🎁 הגעת ל-5 חברים! זכית ב-500 Credits."
            if int(count or 0) >= 5
            else f"🎯 עוד {remaining} חברים להצטרף כדי לקבל 500 Credits."
        )

        text = (
            "🎁 הזמנה ו-Referral\n\n"
            f"🔗 {link}\n\n"
            f"👥 משתמשים שהוזמנו: {count}\n"
            f"🎯 {milestone}\n"
            f"💰 עמלה שנרשמה: {commission}\n\n"
            "העמלה המוצגת כאן נלקחת מספר העמלות של המערכת. "
            "היא אינה הבטחה לרווח עתידי."
        )
        bot.reply_to(msg, text)
