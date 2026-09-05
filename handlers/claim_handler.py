"""SLH Claim + Deposit Address"""
import json
from pathlib import Path
from core.deposit_monitor import verify_bnb_deposit
from core.onchain_claim_authority import record_bnb_deposit


def _load_db():
    return json.loads(Path("state/db.json").read_text(encoding="utf-8"))


def register(bot, context=None):
    @bot.message_handler(commands=["deposit_address"])
    def deposit_address_cmd(m):
        db = _load_db()
        bsc = db.get("bsc_settings", {})
        addr = bsc.get("treasury_wallet", "לא הוגדר")
        bot.reply_to(m, f"💠 כתובת הפקדה (BNB):\n{addr}\n\nהפקד BNB וקבל tx hash.\nואז שלח: /claim <tx_hash>")

    @bot.message_handler(commands=["claim"])
    def claim_cmd(m):
        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, "שימוש: /claim <tx_hash>")
            return

        tx_hash = parts[1].strip()
        uid = str(m.from_user.id)

        res = verify_bnb_deposit(tx_hash)
        if not res.get("ok"):
            bot.reply_to(m, f"❌ ההפקדה לא אומתה: {res}")
            return

        credits = int(float(res["amount_bnb"]) * 1000)
        if credits <= 0:
            bot.reply_to(m, "❌ סכום הפקדה לא תקין.")
            return

        try:
            result = record_bnb_deposit(
                uid=uid,
                credits=credits,
                amount_bnb=res["amount_bnb"],
                tx_hash=tx_hash,
                meta={"source": "telegram_claim", "block": res.get("block")},
            )

            if result["status"] == "duplicate":
                bot.reply_to(m, "ℹ️ הטרנזקציה כבר נזקפה בעבר.")
                return

            bot.reply_to(
                m,
                f"✅ נזקפו {credits} credits\n"
                f"💰 יתרה: {result['balance']}\n"
                f"📝 TX: {tx_hash}"
            )
        except Exception as e:
            bot.reply_to(m, f"❌ שגיאה בזיכוי: {e}")

    print("✅ claim_handler loaded")
