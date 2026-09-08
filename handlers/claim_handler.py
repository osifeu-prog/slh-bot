"""SLH Claim + Deposit Address

BNB crediting is intentionally disabled until the claimant can be
cryptographically/verifiably bound to the source deposit address.
"""
import json
from pathlib import Path


def _load_db():
    return json.loads(Path("state/db.json").read_text(encoding="utf-8"))


def register(bot, context=None):
    @bot.message_handler(commands=["deposit_address"])
    def deposit_address_cmd(m):
        bot.reply_to(
            m,
            "⛔ BNB deposits are temporarily paused.\n"
            "Automated crediting will return after verified user-binding is implemented."
        )

    @bot.message_handler(commands=["claim"])
    def claim_cmd(m):
        bot.reply_to(
            m,
            "⛔ /claim מושבת זמנית.\n"
            "אימות TX לבדו אינו מוכיח שההפקדה שייכת לחשבון Telegram המבקש.\n"
            "המסלול יופעל מחדש רק לאחר הוספת user-binding מאומת."
        )

    print("✅ claim_handler loaded (BNB claims disabled pending user-binding)")
