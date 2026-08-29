import os
import state_manager
from core import economy_bridge
from core import economy_service
from core import profile_manager


def register_econ_handlers(bot):

    @bot.message_handler(commands=['balance'])
    def balance(m):
        uid = str(m.from_user.id)
        bal = profile_manager.get_balance(uid)
        bot.send_message(
            m.chat.id,
            f"💰 Your balance: {bal} credits"
        )

    @bot.callback_query_handler(
        func=lambda call: call.data.startswith("buy_")
    )
    def buy_callback(call):

        item = call.data.split("_", 1)[1]
        uid = str(call.from_user.id)

        prices = {
            "ask_credit": 10,
            "premium_agent": 50,
        }

        price = prices.get(item)

        if price is None:
            bot.answer_callback_query(
                call.id,
                "Unknown item."
            )
            return

        try:
            db = state_manager.load_db()

            if uid not in db.get("users", {}):
                bot.answer_callback_query(
                    call.id,
                    "Please /join first."
                )
                return

            referrer_uid = (
                db.get("referred_by", {}).get(uid)
            )

            result = economy_service.purchase_item(
                uid=uid,
                item=item,
                price=price,
                referrer_uid=referrer_uid,
                meta={
                    "source": "telegram_buy",
                },
            )

            bot.answer_callback_query(
                call.id,
                f"✅ Purchased {item}! "
                f"Remaining: {result['credits']} credits"
            )

            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=(
                    f"✅ Purchased {item} for {price} credits.\n"
                    f"Remaining: {result['credits']} credits."
                )
            )

        except ValueError as e:
            if str(e) == "INSUFFICIENT_CREDITS":
                balance_now = profile_manager.get_balance(uid)
                bot.answer_callback_query(
                    call.id,
                    (
                        f"Not enough credits. "
                        f"Need {price}, have {balance_now}."
                    )
                )
                return

            bot.answer_callback_query(
                call.id,
                f"Purchase blocked: {e}"
            )

        except Exception as e:
            bot.answer_callback_query(
                call.id,
                "Purchase failed safely."
            )
            print(f"[ECON] purchase error: {e}")

    @bot.message_handler(commands=['giveme'])
    def giveme(m):
        from admin_utils import is_admin

        if not is_admin(m):
            return

        if os.getenv("SLH_ALPHA_TEST_MODE", "0") != "1":
            bot.send_message(
                m.chat.id,
                "⛔ Test credit grants are disabled in Alpha."
            )
            return

        uid = str(m.from_user.id)

        try:
            balance = economy_service.record_transaction(
                uid=uid,
                amount=50,
                reason="admin:test_grant",
                meta={
                    "source": "giveme",
                },
            )

            bot.send_message(
                m.chat.id,
                f"💰 50 test credits added. Balance: {balance}"
            )

        except Exception as e:
            bot.send_message(
                m.chat.id,
                "❌ Test credit grant failed safely."
            )
            print(f"[ECON] giveme error: {e}")


def register(bot):
    register_econ_handlers(bot)
