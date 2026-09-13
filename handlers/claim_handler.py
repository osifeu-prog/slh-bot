"""BNB deposit address and verified claim route.

A claim is accepted only when the Telegram account has a cryptographically
verified BNB wallet binding and the submitted transaction is a confirmed
transfer to the configured treasury from that exact wallet.
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
            "🔐 לפני /claim יש לאמת בעלות על ארנק BNB דרך ה־Mini App.\n"
            "זיכוי ניתן רק עבור TX מאותו ארנק מאומת אל ה־Treasury."
        )

    @bot.message_handler(commands=["claim"])
    def claim_cmd(m):
        parts = (m.text or "").split(maxsplit=1)
        if len(parts) != 2 or not parts[1].strip():
            bot.reply_to(m, "שימוש: /claim <TX hash>")
            return

        try:
            from core.bnb_deposit_service import settle_bnb_deposit
            result = settle_bnb_deposit(str(m.from_user.id), parts[1].strip())
            bot.reply_to(
                m,
                "✅ הפקדת BNB אומתה וזוכתה.\n"
                f"BNB: {result['amount_bnb']}\n"
                f"Credits: {result['credits']}\n"
                f"Balance: {result['balance_after']}"
            )
        except ValueError as exc:
            bot.reply_to(m, f"⛔ /claim נדחה: {exc}")
        except Exception as exc:
            print(f"[BNB_CLAIM_ERROR] {exc}")
            bot.reply_to(m, "❌ שגיאה באימות ההפקדה. לא בוצע זיכוי.")

    print("✅ claim_handler loaded (BNB claim requires verified wallet binding)")
