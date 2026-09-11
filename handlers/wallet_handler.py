from core import profile_manager
from heb_convert import get_hebrew_date


def register(bot):

    def referral_link(uid):
        try:
            username = getattr(bot.get_me(), "username", None)
            if username:
                return f"https://t.me/{str(username).lstrip('@')}?start=ref_{uid}"
        except Exception:
            pass
        return None

    @bot.message_handler(commands=["wallet"])
    def wallet(msg):
        uid = str(msg.from_user.id)

        user = profile_manager.get_user(uid)
        wallet = user.get("wallet", {})
        referral = user.get("referral", {})
        gamification = user.get("gamification", {})

        credits = wallet.get("credits", 0)
        staked = wallet.get("staked", 0)
        token_balance = wallet.get("token_balance", 0)
        points = gamification.get("points", 0)
        level = gamification.get("level", 1)
        referral_count = referral.get("count", 0)
        commission = referral.get("commission", 0)
        invite = referral_link(uid)

        text = (
            "[בס\"ד]\n\n"
            "💰 SLH Wallet\n\n"
            f"📅 {get_hebrew_date()}\n"
            f"💳 Credits: {credits}\n"
            f"🔒 Staked: {staked}\n"
            f"🪙 SLH Token: {token_balance}\n"
            f"⭐ Points: {points} (Level {level})\n"
            f"👥 Referrals: {referral_count}\n"
            f"💎 Referral commission: {commission}\n\n"
        )

        if invite:
            text += f"🔗 קישור ההזמנה האישי שלך:\n{invite}\n\n"

        text += (
            "📤 העברת Credits: /transfer <uid> <amount>\n"
            "🪙 העברת SLH: /p2p_slh <uid> <amount>\n"
            "⭐ רכישת Credits: /pay\n"
            "📜 היסטוריית תשלומים: /history\n\n"
            "🌐 BNB/TON deposits: מושהים כרגע עד להשלמת user-binding מאומת.\n"
            "המערכת אינה מזכה מטבע קריפטו לפי TX בלבד."
        )

        try:
            with open("branding/SLH_LOGO.txt", "r", encoding="utf-8") as f:
                logo = f.read().strip()
        except Exception:
            logo = ""
        if logo:
            text = logo + "\n\n" + text

        bot.reply_to(msg, text)

    print("wallet_handler loaded")
