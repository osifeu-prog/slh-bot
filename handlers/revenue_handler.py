import json
from pathlib import Path


def _is_real_payment(tx):
    meta = tx.get("meta") or {}
    return meta.get("source") != "fakepay" and not meta.get("test_mode")


def register(bot):
    @bot.message_handler(commands=["revenue"])
    def revenue_cmd(msg):
        from admin_utils import is_admin
        if not is_admin(msg):
            bot.reply_to(msg, "⛔️ Admin only")
            return
        db = json.loads(Path("state/db.json").read_text(encoding="utf-8"))
        transactions = [t for t in db.get("transactions", []) if _is_real_payment(t)]
        total_stars = sum(t.get("stars_paid", 0) for t in transactions)
        total_credits_sold = sum(t.get("credits", 0) for t in transactions if t.get("reason") == "payment:telegram_stars")
        commissions = db.get("commissions", {})
        total_commission = sum(commissions.values())
        text = (
            "📊 Revenue Report\n"
            f"💰 Stars paid: {total_stars}\n"
            f"🎟 Credits sold: {total_credits_sold}\n"
            f"🤝 Commissions paid: {total_commission}\n"
            f"👥 Users: {len(db.get('users', {}))}"
        )
        bot.reply_to(msg, text)
