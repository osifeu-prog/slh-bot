import os
from datetime import datetime, timezone

import state_manager
from core import profile_manager
from telebot.types import LabeledPrice, PreCheckoutQuery

PROVIDER_TOKEN = ""  # Telegram Stars native (XTR)

STARS_PACKS = {
    "100credits": (100, 100, "100 Credits"),
    "500credits": (500, 450, "500 Credits (10% off)"),
    "1000credits": (1000, 800, "1000 Credits (20% off)"),
}


def _stage_stars_payment(payment_record):
    """Durably stage a successful Telegram payment before credit settlement."""
    charge_id = str(payment_record["telegram_payment_charge_id"])

    def mutate(db):
        pending = db.setdefault("pending_stars_payments", {})
        existing = pending.get(charge_id)
        if existing:
            comparable = (
                str(existing.get("uid")) == str(payment_record["uid"])
                and int(existing.get("stars_paid", 0)) == int(payment_record["stars_paid"])
                and int(existing.get("credits", 0)) == int(payment_record["credits"])
                and str(existing.get("currency")) == str(payment_record["currency"])
            )
            if not comparable:
                raise ValueError("PAYMENT_RECORD_CONFLICT")
            return existing

        record = {
            **payment_record,
            "status": "pending",
            "staged_at": datetime.now(timezone.utc).isoformat(),
        }
        pending[charge_id] = record
        return record

    return state_manager.atomic_update(mutate)


def _mark_stars_payment_applied(charge_id, result):
    charge_id = str(charge_id)

    def mutate(db):
        pending = db.setdefault("pending_stars_payments", {})
        record = pending.get(charge_id)
        if not record:
            return None
        record["status"] = "applied"
        record["applied_at"] = datetime.now(timezone.utc).isoformat()
        record["settlement"] = {
            "status": result.get("status"),
            "credits": result.get("credits"),
            "charge_id": result.get("charge_id"),
        }
        return record

    return state_manager.atomic_update(mutate)


def _settle_staged_payment(record):
    from core import economy_service

    result = economy_service.record_stars_payment(
        uid=record["uid"],
        credits=record["credits"],
        stars_paid=record["stars_paid"],
        currency=record["currency"],
        telegram_payment_charge_id=record["telegram_payment_charge_id"],
        provider_payment_charge_id=record.get("provider_payment_charge_id"),
        referrer_uid=None,
        commission_rate=0,
        meta={
            "source": "telegram_successful_payment",
            "invoice_payload": record["invoice_payload"],
            "package_stars": record["package_stars"],
            "package_credits": record["package_credits"],
            "referral_commission": "disabled_alpha",
            "pending_payment_stage": "durable",
        },
    )
    _mark_stars_payment_applied(record["telegram_payment_charge_id"], result)
    return result


def _reconcile_pending_stars_payments():
    """Retry staged payments after a crash or transient settlement failure."""
    db = state_manager.load_db()
    pending = db.get("pending_stars_payments", {})
    records = [
        record for record in pending.values()
        if record.get("status") == "pending"
    ]

    for record in records:
        try:
            result = _settle_staged_payment(record)
            print(
                f"[PAY] reconciled staged Stars payment "
                f"charge_id={record.get('telegram_payment_charge_id')} "
                f"status={result.get('status')}"
            )
        except Exception as e:
            print(
                f"[PAY] pending Stars reconciliation deferred: "
                f"charge_id={record.get('telegram_payment_charge_id')} error={e}"
            )


def register_payment_handlers(bot):
    # Recover any payment that was durably staged but not fully settled before
    # a process crash/restart. Idempotent settlement makes duplicate recovery safe.
    _reconcile_pending_stars_payments()

    @bot.message_handler(commands=['pay'])
    def pay_command(m):
        uid = str(m.from_user.id)
        db = state_manager.load_db()
        if uid not in db.get("users", {}):
            bot.send_message(m.chat.id, "❌ Please /join first.")
            return

        bot.send_message(
            m.chat.id,
            "💎 Credits unlock: AI asks (/ask), premium agents, and more.\n"
            "Choose a package below 👇\n\n"
            "ℹ️ Crypto deposits are temporarily paused while secure user-binding is completed."
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
        pack_id = call.data.split("_", 1)[1]
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
        parts = str(query.invoice_payload or "").split("_")
        if len(parts) != 3 or parts[0] != "credits" or parts[2] != str(query.from_user.id):
            bot.answer_pre_checkout_query(query.id, ok=False, error_message="Invalid payment recipient.")
            return
        try:
            expected_credits = int(parts[1])
        except Exception:
            bot.answer_pre_checkout_query(query.id, ok=False, error_message="Invalid payment package.")
            return

        expected = next(
            ((pack_stars, pack_credits) for pack_stars, pack_credits, _ in STARS_PACKS.values()
             if pack_credits == expected_credits),
            None,
        )
        if (
            expected is None
            or query.currency != "XTR"
            or int(query.total_amount or 0) != expected[0]
        ):
            bot.answer_pre_checkout_query(query.id, ok=False, error_message="Invalid payment details.")
            return

        bot.answer_pre_checkout_query(query.id, ok=True)

    @bot.message_handler(content_types=['successful_payment'])
    def successful_payment(m):
        uid = str(m.from_user.id)
        payment = m.successful_payment

        payload = payment.invoice_payload
        parts = str(payload or "").split("_")

        if len(parts) != 3 or parts[0] != "credits" or parts[2] != uid:
            bot.send_message(m.chat.id, "❌ Invalid payment payload.")
            print(f"[PAY] rejected payload recipient mismatch: uid={uid}")
            return

        try:
            credits = int(parts[1])
        except Exception:
            bot.send_message(m.chat.id, "❌ Error parsing credits.")
            return

        expected = next(
            ((pack_stars, pack_credits) for pack_stars, pack_credits, _ in STARS_PACKS.values()
             if pack_credits == credits),
            None,
        )
        if (
            expected is None
            or str(payment.currency) != "XTR"
            or int(payment.total_amount or 0) != expected[0]
            or not payment.telegram_payment_charge_id
        ):
            bot.send_message(m.chat.id, "❌ Invalid payment details.")
            print(f"[PAY] rejected settlement details: uid={uid}, credits={credits}")
            return

        record = {
            "uid": uid,
            "credits": credits,
            "stars_paid": int(payment.total_amount),
            "currency": str(payment.currency),
            "telegram_payment_charge_id": str(payment.telegram_payment_charge_id),
            "provider_payment_charge_id": payment.provider_payment_charge_id,
            "invoice_payload": payload,
            "package_stars": expected[0],
            "package_credits": expected[1],
        }

        try:
            # Stage first. If settlement crashes after this point, startup
            # reconciliation can safely retry using the Telegram charge ID.
            staged = _stage_stars_payment(record)
            result = _settle_staged_payment(staged)

            if result["status"] == "duplicate":
                bot.send_message(m.chat.id, "ℹ️ This payment was already processed.")
                return

            bot.send_message(
                m.chat.id,
                f"✅ Payment received! {credits} credits added.\n"
                f"Your balance: {result['credits']} credits."
            )

            print(
                f"[PAY] {credits} credits added to {uid}, "
                f"charge_id={result['charge_id']}"
            )

        except Exception as e:
            # The durable pending record remains. Never claim the payment was
            # lost; the next startup reconciliation will retry it idempotently.
            print(
                f"[PAY] settlement deferred safely: "
                f"charge_id={record['telegram_payment_charge_id']} error={e}"
            )
            bot.send_message(
                m.chat.id,
                "⚠️ Payment received but credit settlement is pending. Please try again later or contact /paysupport."
            )

    @bot.message_handler(commands=['paysupport'])
    def paysupport(m):
        bot.send_message(
            m.chat.id,
            "💳 SLH Payment Support\n"
            "For a payment issue, please send:\n"
            "• payment date/time\n"
            "• amount of Stars\n"
            "• payment reference if available\n\n"
            "We will review the transaction and assist."
        )

    @bot.message_handler(commands=['history'])
    def history(m):
        uid = str(m.from_user.id)
        db = state_manager.load_db()
        txs = [t for t in db.get("transactions", []) if t.get("uid") == uid]
        if not txs:
            bot.send_message(m.chat.id, "📜 No transactions yet.")
            return
        msg = "📜 **Your transactions:**\n"
        for tx in txs[-10:]:
            msg += f"▫️ {tx['credits']} credits — {tx['timestamp'][:10]}\n"
        bot.send_message(m.chat.id, msg.strip())

    @bot.message_handler(commands=['revenue'])
    def revenue(m):
        from admin_utils import is_admin
        if not is_admin(m):
            return

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
            balance = economy_service.record_transaction(
                uid=uid,
                amount=100,
                reason="admin:test_payment",
                meta={"source": "fakepay"},
            )
            bot.send_message(m.chat.id, f"💰 100 test credits added. Balance: {balance}")
        except Exception as e:
            bot.send_message(m.chat.id, "❌ Test payment failed safely.")
            print(f"[PAY] fakepay error: {e}")


def register(bot):
    register_payment_handlers(bot)
