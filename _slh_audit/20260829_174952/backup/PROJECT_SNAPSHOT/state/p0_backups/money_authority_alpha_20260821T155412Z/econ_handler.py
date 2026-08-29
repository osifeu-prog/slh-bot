import state_manager
from core import economy_bridge

def register_econ_handlers(bot):
    @bot.message_handler(commands=['balance'])
    def balance(m):
        uid = str(m.from_user.id)
        db = state_manager.load_db()
        bal = profile_manager.get_balance(uid)
        bot.send_message(m.chat.id, f"💰 Your balance: {bal} credits")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
    def buy_callback(call):
        item = call.data.split("_", 1)[1]
        uid = str(call.from_user.id)
        db = state_manager.load_db()
        user = db.get("users", {}).get(uid)
        if not user:
            bot.answer_callback_query(call.id, "Please /join first.")
            return
        balance = profile_manager.get_balance(uid)
        prices = {"ask_credit": 10, "premium_agent": 50}
        price = prices.get(item, 0)
        if price == 0:
            bot.answer_callback_query(call.id, "Unknown item.")
            return
        if balance < price:
            bot.answer_callback_query(call.id, f"Not enough credits. Need {price}, have {balance}.")
            return
        economy_bridge.spend_credits(uid, price)
        if item == "ask_credit":
            user.setdefault("ask_credits", 0)
            user["ask_credits"] += 1
        elif item == "premium_agent":
            user["premium"] = True
        referrer_uid = db.get("referred_by", {}).get(uid)
        if referrer_uid:
            commission = round(price * 0.85, 2)
            economy_bridge.add_credits(referrer_uid, commission)

        state_manager.save_db(db)
        bot.answer_callback_query(call.id, f"✅ Purchased {item}! Remaining: {profile_manager.get_balance(uid)} credits")
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"✅ Purchased {item} for {price} credits.\nRemaining: {profile_manager.get_balance(uid)} credits."
        )

    @bot.message_handler(commands=['giveme'])
    def giveme(m):
        from admin_utils import is_admin
        if not is_admin(m):
            return
        uid = str(m.from_user.id)
        db = state_manager.load_db()
        economy_bridge.add_credits(uid, 50)
        state_manager.save_db(db)
        bot.send_message(m.chat.id, f"💰 50 credits added. Your balance: {profile_manager.get_balance(uid)} credits")


def register(bot):
    register_econ_handlers(bot)


