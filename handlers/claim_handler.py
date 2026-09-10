"""SLH BNB deposit address and claim route.

The on-chain claim route is intentionally disabled until the deposit is
cryptographically/user-account bound. Verifying only that a transaction paid
the treasury is insufficient because another Telegram user could submit the
same public transaction hash and claim the credits first.
"""
import json
from pathlib import Path


def _load_db():
    return json.loads(Path("state/db.json").read_text(encoding="utf-8"))


def register(bot, context=None):
    @bot.message_handler(commands=["deposit_address"])
    def deposit_address_cmd(m):
        db = _load_db()
        bsc = db.get("bsc_settings", {})
        addr = bsc.get("treasury_wallet", "לא הוגדר")
        bot.reply_to(
            m,
            "💠 כתובת הפקדה (BNB):\n"
            f"{addr}\n\n"
            "⚠️ זיכוי אוטומטי לפי TX מושבת זמנית עד להשלמת מנגנון "
            "שיוך הפקדה למשתמש."
        )

    @bot.message_handler(commands=["claim"])
    def claim_cmd(m):
        bot.reply_to(
            m,
            "⛔ /claim מושבת זמנית.\n"
            "אימות TX לבדו אינו מוכיח שההפקדה שייכת לחשבון Telegram המבקש.\n"
            "המסלול יופעל מחדש רק לאחר הוספת user-binding מאומת."
        )

    print("⚠️ claim_handler loaded (BNB claim disabled pending user binding)")
