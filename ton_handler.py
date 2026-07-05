import requests
import state_manager

# Default settings – will be stored in db.json under "ton_settings"
DEFAULT_WALLET = "YOUR_WALLET_ADDRESS"          # ← החלף בכתובת שלך
DEFAULT_RATE = 100                             # 1 TON = 100 Credits
TONCENTER_API = "https://toncenter.com/api/v2" # mainnet
TESTNET = False                                # שנה ל-True לבדיקה

def register_ton_handlers(bot):
    def get_ton_settings():
        db = state_manager.load_db()
        return db.setdefault("ton_settings", {
            "wallet": DEFAULT_WALLET,
            "rate": DEFAULT_RATE,
            "testnet": TESTNET
        })

    def save_ton_settings(settings):
        db = state_manager.load_db()
        db["ton_settings"] = settings
        state_manager.save_db(db)

    @bot.message_handler(commands=['ton'])
    def ton_info(m):
        settings = get_ton_settings()
        wallet = settings["wallet"]
        rate = settings["rate"]
        msg = (
            f"💎 **TON Payments**\n"
            f"Send TON to this address:\n`{wallet}`\n"
            f"Rate: 1 TON = {rate} Credits\n"
            "After sending, use /ton_check <transaction_hash> to verify and get credits."
        )
        bot.send_message(m.chat.id, msg, parse_mode="Markdown")

    @bot.message_handler(commands=['ton_check'])
    def ton_check(m):
        uid = str(m.from_user.id)
        parts = m.text.split()
        if len(parts) < 2:
            bot.send_message(m.chat.id, "Usage: /ton_check <transaction_hash>")
            return
        tx_hash = parts[1]
        settings = get_ton_settings()
        wallet = settings["wallet"]
        testnet = settings.get("testnet", False)
        # Build API URL
        if testnet:
            api_url = "https://testnet.toncenter.com/api/v2"
        else:
            api_url = TONCENTER_API

        # 1. Check transaction exists and is to our wallet
        try:
            resp = requests.get(f"{api_url}/getTransactions?address={wallet}&limit=20&archival=true")
            if resp.status_code != 200:
                bot.send_message(m.chat.id, "❌ Failed to query TON API.")
                return
            data = resp.json()
            if not data.get("ok"):
                bot.send_message(m.chat.id, "❌ TON API error.")
                return
            # Find transaction with matching hash
            tx = None
            for t in data["result"]:
                if t["transaction_id"]["hash"] == tx_hash:
                    tx = t
                    break
            if not tx:
                bot.send_message(m.chat.id, "❌ Transaction not found or not yet confirmed. Wait a minute and try again.")
                return
        except Exception as e:
            bot.send_message(m.chat.id, f"❌ Error: {e}")
            return

        # 2. Check if it's incoming and amount > 0
        if tx["in_msg"]["source"] == wallet:  # outgoing – ignore
            bot.send_message(m.chat.id, "❌ That transaction is outgoing, not a deposit.")
            return
        amount_nano = int(tx["in_msg"]["value"])
        amount_ton = amount_nano / 1e9
        if amount_ton <= 0:
            bot.send_message(m.chat.id, "❌ Invalid amount.")
            return

        # 3. Avoid double credit – check if tx_hash already used
        db = state_manager.load_db()
        used_txs = db.setdefault("used_ton_txs", [])
        if tx_hash in used_txs:
            bot.send_message(m.chat.id, "❌ This transaction was already credited.")
            return

        # 4. Calculate credits
        rate = settings["rate"]
        credits = round(amount_ton * rate, 2)

        # 5. Add to user balance
        user = db.setdefault("users", {}).setdefault(uid, {"balance": 0})
        user["balance"] = user.get("balance", 0) + credits

        # Mark tx as used
        used_txs.append(tx_hash)
        db["used_ton_txs"] = used_txs

        # Record transaction
        db.setdefault("transactions", []).append({
            "uid": uid,
            "credits": credits,
            "type": "ton",
            "ton_amount": amount_ton,
            "tx_hash": tx_hash,
            "timestamp": datetime.utcnow().isoformat()
        })

        state_manager.save_db(db)
        bot.send_message(
            m.chat.id,
            f"✅ TON deposit verified! {credits} credits added.\n"
            f"Amount: {amount_ton} TON\n"
            f"Your balance: {user['balance']} credits."
        )

    @bot.message_handler(commands=['ton_rate'])
    def ton_rate(m):
        from admin_utils import is_admin
        if not is_admin(m):
            return
        parts = m.text.split()
        if len(parts) < 2:
            settings = get_ton_settings()
            bot.send_message(m.chat.id, f"Current rate: 1 TON = {settings['rate']} Credits.")
            return
        try:
            new_rate = float(parts[1])
            settings = get_ton_settings()
            settings["rate"] = new_rate
            save_ton_settings(settings)
            bot.send_message(m.chat.id, f"✅ TON rate updated: 1 TON = {new_rate} Credits.")
        except:
            bot.send_message(m.chat.id, "Invalid rate.")

    @bot.message_handler(commands=['ton_set_wallet'])
    def ton_set_wallet(m):
        from admin_utils import is_admin
        if not is_admin(m):
            return
        parts = m.text.split()
        if len(parts) < 2:
            bot.send_message(m.chat.id, "Usage: /ton_set_wallet <address>")
            return
        new_wallet = parts[1]
        settings = get_ton_settings()
        settings["wallet"] = new_wallet
        save_ton_settings(settings)
        bot.send_message(m.chat.id, f"✅ Wallet updated.")
