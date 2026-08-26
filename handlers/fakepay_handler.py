from core import economy_service

def register(bot):
    @bot.message_handler(commands=["fakepay"])
    def fakepay_cmd(msg):
        if str(msg.from_user.id) != "8789977826":
            bot.reply_to(msg, "⛔️ Admin only")
            return
        parts = msg.text.split()
        amount = int(parts[1]) if len(parts) > 1 else 100
        res = economy_service.record_stars_payment(
            uid=str(msg.from_user.id),
            credits=amount,
            stars_paid=amount,
            currency="XTR",
            telegram_payment_charge_id=f"fakepay_{msg.from_user.id}",
            provider_payment_charge_id=f"fakepay_{msg.from_user.id}"
        )
        bot.reply_to(msg, f"✅ זוכו {amount} credits. יתרה: {res['credits']}")
