import json

DB_PATH = "state/db.json"

BSC_RPC = "https://bsc-dataseed.binance.org/"
CONTRACT = "0xACb0A09414CEA1C879c67bB7A877E4e19480f022"


def get_balance(uid):
    try:
        from core import profile_manager

        user = profile_manager.get_user(str(uid))

        return (
            user
            .get("wallet", {})
            .get("token_balance", 0)
        )

    except Exception as e:
        print("TOKEN BALANCE ERROR:", e)
        return 0


def get_supply():
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            db = json.load(f)

        total = 0

        for user in db.get("users", {}).values():
            total += user.get("wallet", {}).get("token_balance", 0)

        return total

    except Exception as e:
        print("TOKEN SUPPLY ERROR:", e)
        return 0


def register(bot):

    @bot.message_handler(commands=['token'])
    def token_cmd(m):

        parts = m.text.split()

        if len(parts) < 2:
            bot.reply_to(
                m,
                "Options: /token supply | /token balance [user_id]"
            )
            return

        sub = parts[1].lower()

        if sub == "supply":

            bot.reply_to(
                m,
                f"💰 Total Supply: {get_supply():,.4f} SLH"
            )

        elif sub == "balance":

            uid = (
                parts[2]
                if len(parts) > 2
                else str(m.from_user.id)
            )

            bal = get_balance(uid)

            bot.reply_to(
                m,
                f"💰 Balance: {bal:,.4f} SLH"
            )

        else:

            bot.reply_to(
                m,
                "Options: /token supply | /token balance [user_id]"
            )
