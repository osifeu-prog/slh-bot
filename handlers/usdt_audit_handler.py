"""Read-only USDT-on-TON audit command.

No balance mutation and no transaction broadcast occurs here.
"""
from core.bnb_gate import CLOSED_MESSAGE


def register(bot):
    @bot.message_handler(commands=["usdt_check"])
    def usdt_check_cmd(msg):
        parts = (msg.text or "").split(maxsplit=1)
        if len(parts) != 2 or not parts[1].strip():
            bot.reply_to(msg, "שימוש: /usdt_check <TX hash>")
            return

        try:
            from core.usdt_audit_service import audit_usdt_tx
            result = audit_usdt_tx(str(msg.from_user.id), parts[1].strip())
            if not result.get("match"):
                bot.reply_to(
                    msg,
                    "🔎 לא נמצאה עסקת USDT תואמת בין ה־100 העברות האחרונות "
                    "שנבדקו.\nלא בוצע זיכוי."
                )
                return

            t = result["transfer"]
            bot.reply_to(
                msg,
                "🔎 USDT audit — ללא זיכוי\n"
                f"Amount: {t['amount_usdt']} USDT\n"
                f"From: {t['source']}\n"
                f"To: {t['destination']}\n"
                f"Bound wallet match: {'✅' if t['source_bound_wallet'] else '❌'}\n"
                f"Treasury match: {'✅' if t['destination_treasury'] else '❌'}\n"
                f"Aborted: {'✅' if t['transaction_aborted'] else '❌'}\n"
                f"Jetton Master: {t['jetton_master']}\n"
                f"TX: {t['transaction_hash']}\n\n"
                "ℹ️ הבדיקה אינה מזכה Credits."
            )
        except ValueError as exc:
            bot.reply_to(msg, f"⛔ USDT audit: {exc}")
        except Exception as exc:
            print(f"[USDT_AUDIT] {type(exc).__name__}: {str(exc)[:200]}")
            bot.reply_to(msg, "⚠️ לא ניתן לבצע את בדיקת ה-USDT כרגע.")


    print("✅ usdt_audit_handler loaded")
