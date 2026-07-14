import json, time

DB_PATH = "state/db.json"

def get_db():
    with open(DB_PATH, "r") as f:
        return json.load(f)

def save_db(db):
    with open(DB_PATH, "w") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

def register(bot):
    @bot.message_handler(commands=['stake_deposit'])
    def stake_deposit(msg):
        uid = str(msg.from_user.id)
        args = msg.text.split()
        if len(args) < 2:
            bot.reply_to(msg, "Usage: /stake_deposit <amount>")
            return
        try:
            amount = float(args[1])
        except:
            bot.reply_to(msg, "Invalid amount.")
            return

        db = get_db()
        token = db.setdefault("token", {})
        balances = token.setdefault("balances", {})
        if balances.get(uid, 0) < amount:
            bot.reply_to(msg, "Insufficient balance.")
            return

        balances[uid] -= amount
        staking = db.setdefault("staking", {})
        user_stake = staking.setdefault(uid, {"amount": 0, "since": time.time()})
        user_stake["amount"] += amount
        save_db(db)
        bot.reply_to(msg, f"🔒 Staked {amount} SLH. Total staked: {user_stake['amount']:.2f}")

    @bot.message_handler(commands=['stake_claim'])
    def stake_claim(msg):
        uid = str(msg.from_user.id)
        db = get_db()
        staking = db.get("staking", {}).get(uid)
        if not staking or staking["amount"] <= 0:
            bot.reply_to(msg, "No active stake.")
            return

        # 5% reward per hour (demo)
        elapsed_hours = (time.time() - staking["since"]) / 3600
        reward = staking["amount"] * 0.05 * elapsed_hours
        staking["amount"] += reward
        staking["since"] = time.time()

        token = db.setdefault("token", {})
        balances = token.setdefault("balances", {})
        save_db(db)
        bot.reply_to(msg, f"🎉 Reward added: {reward:.4f} SLH. New stake: {staking['amount']:.2f}")

    @bot.message_handler(commands=['stake_info'])
    def stake_info(msg):
        uid = str(msg.from_user.id)
        db = get_db()
        staking = db.get("staking", {}).get(uid, {})
        amount = staking.get("amount", 0)
        since = staking.get("since", 0)
        if since:
            elapsed = (time.time() - since) / 3600
            bot.reply_to(msg, f"🔒 Staked: {amount:.2f} SLH\n⏱ Staking for: {elapsed:.1f} hours")
        else:
            bot.reply_to(msg, "No active stake.")
