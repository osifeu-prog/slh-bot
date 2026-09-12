import json
from pathlib import Path


def _real_stars_transactions(db):
    """Return transactions backed by canonical real Telegram Stars ledger entries."""
    transactions = db.get("transactions", [])
    ledger = db.get("ledger", [])
    real_charge_ids = set()

    for entry in ledger:
        if entry.get("reason") != "payment:telegram_stars":
            continue
        meta = entry.get("meta") or {}
        if meta.get("source") != "telegram_successful_payment":
            continue
        if meta.get("currency") != "XTR":
            continue
        charge_id = str(meta.get("charge_id") or "").strip()
        if charge_id:
            real_charge_ids.add(charge_id)

    result = []
    for tx in transactions:
        charge_id = str(tx.get("telegram_payment_charge_id") or tx.get("charge_id") or "").strip()
        if charge_id and charge_id in real_charge_ids:
            result.append(tx)
    return result


def register(bot):
    @bot.message_handler(commands=["revenue"])
    def revenue_cmd(msg):
        from admin_utils import is_admin
        if not is_admin(msg):
            bot.reply_to(msg, "⛔️ Admin only")
            return

        db = json.loads(Path("state/db.json").read_text(encoding="utf-8"))
        transactions = _real_stars_transactions(db)
        total_stars = sum(t.get("stars_paid", 0) for t in transactions)
        total_credits_sold = sum(t.get("credits", 0) for t in transactions)
        paying_customers = len({str(t.get("uid")) for t in transactions if t.get("uid")})
        commissions = db.get("commissions", {})
        total_commission = sum(commissions.values())

        text = (
            "📊 SLH Revenue\n"
            f"💰 Real Stars received: {total_stars}\n"
            f"🎟 Credits sold: {total_credits_sold}\n"
            f"🤝 Commissions paid: {total_commission}\n"
            f"👥 Paying customers: {paying_customers}"
        )
        bot.reply_to(msg, text)
