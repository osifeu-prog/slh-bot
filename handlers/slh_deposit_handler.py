"""SLH Live (BEP-20) deposit claim.

This route only settles an already-confirmed on-chain transfer from the user's
verified BNB/BSC wallet to the configured SLH Treasury. It never sends funds.
"""
from core.bnb_gate import CLOSED_MESSAGE, bnb_settlement_allowed


def register(bot):
    @bot.message_handler(commands=["claim_slh"])
    def claim_slh_cmd(msg):
        if not bnb_settlement_allowed(msg.from_user.id):
            bot.reply_to(msg, CLOSED_MESSAGE)
            return

        parts = (msg.text or "").split(maxsplit=1)
        if len(parts) != 2 or not parts[1].strip():
            bot.reply_to(msg, "שימוש: /claim_slh <TX hash>")
            return

        tx_hash = parts[1].strip()
        try:
            from core.slh_deposit_service import settle_slh_deposit
            result = settle_slh_deposit(str(msg.from_user.id), tx_hash)
            if result.get("status") == "duplicate":
                bot.reply_to(
                    msg,
                    "♻️ ה־SLH Live כבר זוכה בעבר.\n"
                    f"TX: {result['tx_hash']}\n"
                    f"SLH Live: {result.get('live_token_balance', 0)}"
                )
                return

            bot.reply_to(
                msg,
                "✅ הפקדת SLH Live אומתה וזוכתה.\n"
                f"Amount: {result['amount_slh']} SLH\n"
                f"Live balance: {result['live_token_balance']} SLH\n"
                f"Confirmations: {result['confirmations']}\n"
                f"TX: {result['tx_hash']}"
            )
        except ValueError as exc:
            bot.reply_to(msg, f"⛔ /claim_slh נדחה: {exc}")
        except Exception as exc:
            print(f"[SLH_CLAIM_ERROR] {type(exc).__name__}: {str(exc)[:200]}")
            bot.reply_to(msg, "❌ שגיאה באימות הפקדת SLH. לא בוצע זיכוי.")

    print("✅ slh_deposit_handler loaded")
