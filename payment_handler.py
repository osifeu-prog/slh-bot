import state_manager
from telebot.types import LabeledPrice, PreCheckoutQuery
from datetime import datetime

PROVIDER_TOKEN = ""  # Telegram Stars native (XTR)

STARS_PACKS = {
    "100credits": (100, 100, "100 Credits"),
    "500credits": (500, 450, "500 Credits (10% off)"),
    "1000credits": (1000, 800, "1000 Credits (20% off)"),
}

def register_payment_handlers(bot):

    @bot.message_handler(commands=['pay'])
    def pay_command(m):
        uid = str(m.from_user.id)
        db = state_manager.load_db()
        if uid not in db.get("users", {}):
            bot.send_message(m.chat.id, "❌ Please /join first.")
            return

        # Explain what you can buy with credits
        bot.send_message(
            m.chat.id,
            "💎 Credits unlock: AI asks (/ask), premium agents, and more.\n"
            "Choose a package below 👇"
        )

        from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
        markup = InlineKeyboardMarkup(row_width=1)
        for pack_id, (stars, credits, label) in STARS_PACKS.items():
            markup.add(InlineKeyboardButton(
                text=f"⭐ {stars} Stars → {credits} Credits ({label})",
                callback_data=f"pay_{pack_id}"
            ))
        bot.send_message(m.chat.id, "💰 Select a credits package:", reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("pay_"))
    def payment_callback(call):
        pack_id = call.data.split("_")[1]
        if pack_id not in STARS_PACKS:
            bot.answer_callback_query(call.id, "Invalid package.")
            return
        stars, credits, label = STARS_PACKS[pack_id]
        prices = [LabeledPrice(label=label, amount=stars)]
        try:
            bot.send_invoice(
                chat_id=call.message.chat.id,
                title="SLH Credits",
                description=f"Add {credits} credits to your SLH account",
                invoice_payload=f"credits_{credits}_{call.from_user.id}",
                provider_token=PROVIDER_TOKEN,
                currency="XTR",
                prices=prices,
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
        bot.answer_pre_checkout_query(query.id, ok=True)

    @bot.message_handler(content_types=['successful_payment'])
    def successful_payment(m):
        uid = str(m.from_user.id)
        charge_id = m.successful_payment.telegram_payment_charge_id
        print(f"[PAY] Successful payment from {uid}, payload={m.successful_payment.invoice_payload}, charge_id={charge_id}")
        payload = m.successful_payment.invoice_payload
        parts = payload.split("_")
        if len(parts) != 3 or parts[0] != "credits":
            bot.send_message(m.chat.id, "❌ Invalid payment payload.")
            return
        try:
            credits = int(parts[1])
        except:
            bot.send_message(m.chat.id, "❌ Error parsing credits.")
            return

        db = state_manager.load_db()

        existing_charge_ids = {t.get("telegram_payment_charge_id") for t in db.get("transactions", [])}
        if charge_id in existing_charge_ids:
            print(f"[PAY] DUPLICATE payment ignored, charge_id={charge_id}, uid={uid}")
            bot.send_message(m.chat.id, "ℹ️ This payment was already processed.")
            return

        user = db.setdefault("users", {}).setdefault(uid, {"balance": 0})
        user["balance"] = user.get("balance", 0) + credits

        # Referrer commission
        referrer_uid = db.get("referred_by", {}).get(uid)
        if referrer_uid:
            commission = round(credits * 0.85, 2)
            ref_user = db.setdefault("users", {}).setdefault(referrer_uid, {"balance": 0})
            ref_user["balance"] = ref_user.get("balance", 0) + commission
            db.setdefault("commissions", {}).setdefault(referrer_uid, 0)
            db["commissions"][referrer_uid] += commission
            print(f"[PAY] Commission {commission} to referrer {referrer_uid}")
            try:
                bot.send_message(
                    int(referrer_uid),
                    f"🎉 Your friend just purchased credits! You earned {commission} credits."
                )
            except Exception as e:
                print(f"[PAY] Failed to notify referrer {referrer_uid}: {e}")

        trans = {
            "uid": uid,
            "credits": credits,
            "stars_paid": m.successful_payment.total_amount,
            "currency": m.successful_payment.currency,
            "telegram_payment_charge_id": charge_id,
            "provider_payment_charge_id": m.successful_payment.provider_payment_charge_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        db.setdefault("transactions", []).append(trans)

        try:
            state_manager.save_db(db)
        except Exception as e:
            print(f"[PAY] CRITICAL: save_db failed AFTER payment charged! uid={uid}, charge_id={charge_id}, credits={credits}, error={e}")
            bot.send_message(m.chat.id, "⚠️ Payment received but there was an error saving your credits. Please contact support with this reference: " + charge_id)
            try:
                bot.send_message(8789977826, f"🚨 PAYMENT SAVE FAILED uid={uid} charge_id={charge_id} credits={credits} error={e}")
            except Exception:
                pass
            return

        bot.send_message(
            m.chat.id,
            f"✅ Payment received! {credits} credits added.\n"
            f"Your balance: {user['balance']} credits.\n"
            "Use /buy to unlock features like /ask or premium agents."
        )
        print(f"[PAY] {credits} credits added to {uid}, new balance {user['balance']}")

    @bot.message_handler(commands=['history'])
    def history(m):
        uid = str(m.from_user.id)
        db = state_manager.load_db()
        txs = [t for t in db.get("transactions", []) if t.get("uid") == uid]
        if not txs:
            bot.send_message(m.chat.id, "📜 No transactions yet.")
            return
        msg = "📜 **Your transactions:**\n"
        for tx in txs[-10:]:  # show last 10
            msg += f"▫️ {tx['credits']} credits — {tx['timestamp'][:10]}\n"
        bot.send_message(m.chat.id, msg.strip())

    @bot.message_handler(commands=['revenue'])
    def revenue(m):
        # Admin only? We'll keep open but can protect with is_admin if needed
        db = state_manager.load_db()
        txs = db.get("transactions", [])
        total_stars = sum(tx.get("stars_paid", 0) for tx in txs)
        total_credits = sum(tx.get("credits", 0) for tx in txs)
        total_commissions = sum(db.get("commissions", {}).values())
        bot.send_message(
            m.chat.id,
            f"💰 **Revenue**\n"
            f"Total transactions: {len(txs)}\n"
            f"Total Stars received: {total_stars}\n"
            f"Total credits issued: {total_credits}\n"
            f"Total commissions paid: {total_commissions}"
        )

    @bot.message_handler(commands=['fakepay'])
    def fakepay(m):
        # Admin only
        from admin_utils import is_admin
        if not is_admin(m):
            return
        uid = str(m.from_user.id)
        db = state_manager.load_db()
        user = db.setdefault("users", {}).setdefault(uid, {"balance": 0})
        user["balance"] = user.get("balance", 0) + 100
        state_manager.save_db(db)
        bot.send_message(m.chat.id, f"💰 (Fake) 100 credits added. Balance: {user['balance']}")
        print(f"[FAKEPAY] 100 credits added to {uid}")
