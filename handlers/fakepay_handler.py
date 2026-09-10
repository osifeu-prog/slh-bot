import os

from core import economy_service


def register(bot):
    @bot.message_handler(commands=["fakepay"])
    def fakepay_cmd(msg):
        # Test-only minting endpoint. Never available in normal Alpha/production.
        from admin_utils import is_admin

        if not is_admin(msg):
            bot.reply_to(msg, "⛔️ Admin only")
            return

        if os.getenv("SLH_ALPHA_TEST_MODE", "0") != "1":
            bot.reply_to(msg, "⛔️ Fake payments are disabled outside test mode.")
            return

        parts = msg.text.split()
        try:
            amount = int(parts[1]) if len(parts) > 1 else 100
        except (TypeError, ValueError):
            bot.reply_to(msg, "❌ Invalid amount.")
            return

        if amount <= 0 or amount > 10000:
            bot.reply_to(msg, "❌ Test amount must be between 1 and 10000 credits.")
            return

        try:
            res = economy_service.record_stars_payment(
                uid=str(msg.from_user.id),
                credits=amount,
                stars_paid=amount,
                currency="XTR",
                telegram_payment_charge_id=f"fakepay:{msg.from_user.id}:{msg.message_id}",
                provider_payment_charge_id=f"fakepay:{msg.from_user.id}:{msg.message_id}",
                meta={"source": "fakepay", "test_mode": True},
            )
            bot.reply_to(msg, f"✅ זוכו {amount} test credits. יתרה: {res['credits']}")
        except Exception as exc:
            bot.reply_to(msg, "❌ Test payment failed safely.")
            print(f"[FAKEPAY] error: {type(exc).__name__}")
