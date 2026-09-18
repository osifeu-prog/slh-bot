"""Telegram handlers for Revenue Share staking."""
import state_manager
from core import staking_revenue_share as rs


def register(bot, context=None):

    @bot.message_handler(commands=["stake_revenue"])
    def stake_revenue_cmd(m):
        parts = (m.text or "").split()
        if len(parts) != 2:
            bot.reply_to(m, "Usage: /stake_revenue <amount_slh>")
            return
        try:
            amount = float(parts[1])
        except ValueError:
            bot.reply_to(m, "Invalid amount")
            return
        try:
            r = rs.stake(m.from_user.id, amount)
            bot.reply_to(m,
                "Staked {a} SLH\nUnlock: {u}\n\n"
                "You are now eligible for quarterly revenue share.\n"
                "80% of net ESP revenue distributed pro-rata.\n"
                "This is NOT a guaranteed yield. If revenue is 0, distribution is 0.".format(
                    a=r["principal"], u=r["unlock_at"][:10]))
        except ValueError as e:
            bot.reply_to(m, "Error: " + str(e))

    @bot.message_handler(commands=["claim_revenue"])
    def claim_revenue_cmd(m):
        try:
            r = rs.claim(m.from_user.id)
            bot.reply_to(m, "Claimed {a:.4f} SLH\nNew balance: {b:.4f}".format(
                a=r["claimed"], b=r["new_balance"]))
        except ValueError as e:
            bot.reply_to(m, "Error: " + str(e))

    @bot.message_handler(commands=["my_stake"])
    def my_stake_cmd(m):
        db = state_manager.load_db()
        uid = str(m.from_user.id)
        pos = db.get("staking_positions", {}).get(uid)
        if not pos:
            bot.reply_to(m, "No active revenue share position.")
            return
        user = db.get("users", {}).get(uid, {})
        wallet = user.get("wallet", {})
        bot.reply_to(m,
            "Revenue Share Position\n\n"
            "Principal: {p} SLH\n"
            "Staked at: {s}\n"
            "Unlocks: {u}\n"
            "Total received: {r}\n"
            "Claimable now: {c}\n"
            "Available balance: {b}".format(
                p=pos["principal"], s=pos["staked_at"][:10], u=pos["unlock_at"][:10],
                r=pos.get("total_received", 0),
                c=wallet.get("revenue_share_claimable", 0),
                b=wallet.get("token_balance", 0)))

    print("staking_revenue_handler loaded")
