import json

DB_PATH = "state/db.json"

BSC_RPC = "https://bsc-dataseed.binance.org/"
CONTRACT = "0xYourTokenContract"


def get_balance(wallet):
    try:
        with open(DB_PATH, "r") as f:
            db = json.load(f)
        return db.get("token", {}).get("balances", {}).get(wallet, 0)
    except:
        return 0


def get_supply():
    try:
        with open(DB_PATH, "r") as f:
            db = json.load(f)
        return db.get("token", {}).get("supply", 0)
    except:
        return 0


def register(bot):

    @bot.message_handler(commands=['token'])
    def token_cmd(m):

        parts = m.text.split()

        if len(parts) < 2:
            bot.reply_to(
                m,
                "Options: /token supply | /token balance [wallet]"
            )
            return

        sub = parts[1].lower()

        if sub == "supply":
            bot.reply_to(
                m,
                f"💰 Total Supply: {get_supply():,.2f} SLH"
            )

        elif sub == "balance":

            wallet = parts[2] if len(parts) > 2 else str(m.from_user.id)

            bal = get_balance(wallet)

            if bal is not None:
                msg = f"💰 Balance: {bal:,.4f} SLH"
            else:
                msg = "❌ Error"

            bot.reply_to(m, msg)

        else:
            bot.reply_to(
                m,
                "Options: /token supply | /token balance [wallet]"
            )
