from core import profile_manager


def register(bot):

    @bot.message_handler(commands=["wallet"])
    def wallet(msg):
        uid = str(msg.from_user.id)

        user = profile_manager.get_user(uid)
        wallet = user.get("wallet", {})

        credits = wallet.get("credits", 0)
        staked = wallet.get("staked", 0)
        token_balance = wallet.get("token_balance", 0)

        text = (
            "[בס\"ד]\n\n"
            "💰 SLH Wallet\n\n"
            f"👤 User: {uid}\n"
            f"💳 Credits: {credits}\n"
            f"🔒 Staked: {staked}\n"
            f"🪙 Token Balance: {token_balance}\n"
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
