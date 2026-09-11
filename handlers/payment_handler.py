import os
import state_manager
from core import profile_manager
from telebot.types import LabeledPrice, PreCheckoutQuery

PROVIDER_TOKEN = ""

STARS_PACKS = {
    "100credits": (100, 100, "100 Credits"),
    "500credits": (500, 450, "500 Credits (10% off)"),
    "1000credits": (1000, 800, "1000 Credits (20% off)"),
}


def _is_real_payment(tx):
    meta = tx.get("meta") or {}
    return meta.get("source") != "fakepay" and not meta.get("test_mode")


def register_payment_handlers(bot):
    @bot.message_handler(commands=['pay'])
    def pay_command(m):
        uid = str(m.from_user.id)
        db = state_manager.load_db()
        if uid not in db.get("users", {}):
            bot.send_message(m.chat.id, "❌ Please /join first.")
            return
        bot.send_message(m.chat.id, "💎 Credits unlock: AI asks (/ask), premium agents, and more.\nChoose a package below 👇")
        from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
        markup = InlineKeyboardMarkup(row_width=1)
        for pack_id, (stars, credits, label) in STARS_PACKS.items():
            markup.add(InlineKeyboardButton(text=f"⭐ {stars} Stars → {credits} Credits ({label})", callback_data=f"pay_{pack_id}"))
        bot.send_message(m.chat.id, "💰 Select a credits package:", reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("pay_"))
    def payment_callback(call):
        pack_id = call.data.split("_", 1)[1]
        if pack_id not in STARS_PACKS:
            bot.answer_callback_query(call.id, "Invalid package.")
            return
        stars, credits, label = STARS_PACKS[pack_id]
        try:
            bot.send_invoice(
                chat_id=call.message.chat.id,
                title="SLH Credits",
                description=f"Add {credits} credits to your SLH account",
                invoice_payload=f"credits_{credits}_{call.from_user.id}",
                provider_token=PROVIDER_TOKEN,
                currency="XTR",
                prices=[LabeledPrice(label=label, amount=stars)],
                start_parameter=f"credits_{credits}",
                need_name=False,
                need_phone_number=False,
                need_email=False,
                is_flexible=False
            )
            bot.answer_callback_query(call.id)
            print(f"[PAY] Invoice sent to {call.from_user.id} for {stars} Stars")
        except Exception as e:
            print(f"[PAY] Error sending invoice: {e}")
            bot.answer_callback_query(call.id, "Failed to send invoice. Try again later.")

    @bot.pre_checkout_query_handler(func=lambda query: True)
    def pre_checkout(query: PreCheckoutQuery):
        print(f"[PAY] Pre-checkout query from {query.from_user.id}, payload={query.invoice_payload}")
        parts = str(query.invoice_payload or "").split("_")
        if len(parts) != 3 or parts[0] != "credits" or parts[2] != str(query.from_user.id):
            bot.answer_pre_checkout_query(query.id, ok=False, error_message="Invalid payment recipient.")
            return
        try:
            expected_credits = int(parts[1])
        except Exception:
            bot.answer_pre_checkout_query(query.id, ok=False, error_message="Invalid payment package.")
            return
        if expected_credits <= 0 or query.currency != "XTR" or not query.total_amount:
            bot.answer_pre_checkout_query(query.id, ok=False, error_message="Invalid payment details.")
            return
        bot.answer_pre_checkout_query(query.id, ok=True)

    @bot.message_handler(content_types=['successful_payment'])
    def successful_payment(m):
        uid = str(m.from_user.id)
        payment = m.successful_payment
        payload = payment.invoice_payload
        parts = payload.split("_")
        if len(parts) != 3 or parts[0] != "credits" or parts[2] != uid:
            bot.send_message(m.chat.id, "❌ Invalid payment payload.")
            print(f"[PAY] rejected payload recipient mismatch: uid={uid}")
            return
        try:
            credits = int(parts[1])
        except Exception:
            bot.send_message(m.chat.id, "❌ Error parsing credits.")
            return
        try:
            db = state_manager.load_db()
            referrer_uid = db.get("users", {}).get(uid, {}).get("referral", {}).get("referred_by")
            from core import economy_service
            result = economy_service.record_stars_payment(
                uid=uid,
                credits=credits,
                stars_paid=payment.total_amount,
                currency=payment.currency,
                telegram_payment_charge_id=payment.telegram_payment_charge_id,
                provider_payment_charge_id=payment.provider_payment_charge_id,
                referrer_uid=referrer_uid,
                meta={"source": "telegram_successful_payment", "invoice_payload": payload},
            )
            if result["status"] == "duplicate":
                bot.send_message(m.chat.id, "ℹ️ This payment was already processed.")
                return
            bot.send_message(m.chat.id, f"✅ Payment received! {credits} credits added.\nYour balance: {result['credits']} credits.")
            print(f"[PAY] {credits} credits added, charge_id={result['charge_id']}")
        except Exception as e:
            print(f"[PAY] Atomic payment failed: {type(e).__name__}")
            bot.send_message(m.chat.id, "⚠️ Payment processing failed safely. Please contact /paysupport.")

    @bot.message_handler(commands=['paysupport'])
    def paysupport(m):
        bot.send_message(m.chat.id, "💳 SLH Payment Support\nFor a payment issue, send the payment date/time, Stars amount, and payment reference if available.")

    @bot.message_handler(commands=['history'])
    def history(m):
        uid = str(m.from_user.id)
        db = state_manager.load_db()
        txs = [t for t in db.get("transactions", []) if t.get("uid") == uid]
        if not txs:
            bot.send_message(m.chat.id, "📜 No transactions yet.")
            return
        msg = "📜 Your transactions:\n"
        for tx in txs[-10:]:
            msg += f"▫️ {tx.get('credits', 0)} credits — {str(tx.get('timestamp', ''))[:10]}\n"
        bot.send_message(m.chat.id, msg.strip())

    @bot.message_handler(commands=['revenue'])
    def revenue(m):
        from admin_utils import is_admin
        if not is_admin(m):
            return
        db = state_manager.load_db()
        txs = [tx for tx in db.get("transactions", []) if _is_real_payment(tx)]
        total_stars = sum(tx.get("stars_paid", 0) for tx in txs)
        total_credits = sum(tx.get("credits", 0) for tx in txs if tx.get("reason") == "payment:telegram_stars")
        total_commissions = sum(db.get("commissions", {}).values())
        bot.send_message(m.chat.id, f"💰 Revenue\nTotal transactions: {len(txs)}\nTotal Stars received: {total_stars}\nTotal credits issued: {total_credits}\nTotal commissions paid: {total_commissions}")

    @bot.message_handler(commands=['fakepay_disabled'])
    def fakepay(m):
        from admin_utils import is_admin
        if not is_admin(m):
            return
        if os.getenv("SLH_ALPHA_TEST_MODE", "0") != "1":
            bot.send_message(m.chat.id, "⛔ Fake payments are disabled in Alpha.")
            return
        uid = str(m.from_user.id)
        try:
            from core import economy_service
            balance = economy_service.record_transaction(uid=uid, amount=100, reason="admin:test_payment", meta={"source": "fakepay", "test_mode": True})
            bot.send_message(m.chat.id, f"💰 100 test credits added. Balance: {balance}")
        except Exception as e:
            bot.send_message(m.chat.id, "❌ Test payment failed safely.")
            print(f"[PAY] fakepay error: {type(e).__name__}")


def register(bot):
    register_payment_handlers(bot)
