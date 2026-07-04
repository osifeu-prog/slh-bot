import state_manager

def register_econ_handlers(bot):
    @bot.message_handler(commands=['balance'])
    def balance(m):
        uid = str(m.from_user.id)
        db = state_manager.load_db()
        bal = db.get("users", {}).get(uid, {}).get("balance", 0)
        bot.send_message(m.chat.id, f"💰 Your balance: {bal} credits")

    @bot.message_handler(commands=['buy'])
    def buy(m):
        uid = str(m.from_user.id)
        parts = m.text.split()
        if len(parts) < 2:
            bot.send_message(m.chat.id, "Usage: /buy <item>")
            return
        item = parts[1]
        db = state_manager.load_db()
        user = db.get("users", {}).get(uid)
        if not user:
            bot.send_message(m.chat.id, "Please /join first.")
            return
        balance = user.get("balance", 0)
        prices = {"ask_credit": 10, "premium_agent": 50}
        price = prices.get(item, 0)
        if price == 0:
            bot.send_message(m.chat.id, "Unknown item.")
            return
        if balance < price:
            bot.send_message(m.chat.id, f"Not enough credits. Need {price}, have {balance}.")
            return
        user["balance"] = balance - price
        if item == "ask_credit":
            user.setdefault("ask_credits", 0)
            user["ask_credits"] += 1
        elif item == "premium_agent":
            user["premium"] = True
        state_manager.save_db(db)
        bot.send_message(m.chat.id, f"✅ Purchased {item}! Remaining: {user['balance']} credits")

    @bot.message_handler(commands=['giveme'])
    def giveme(m):
        uid = str(m.from_user.id)
        db = state_manager.load_db()
        db.setdefault("users", {}).setdefault(uid, {})["balance"] = db.get("users", {}).get(uid, {}).get("balance", 0) + 50
        state_manager.save_db(db)
        bot.send_message(m.chat.id, f"💰 50 credits added. Your balance: {db['users'][uid]['balance']} credits")
