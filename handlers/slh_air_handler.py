"""SLH Alpha AIR distribution handler.

Uses the canonical SLH Distribution Authority. This command transfers
existing SLH; it does not mint supply.
"""

from core.authority import require_permission
from core.slh_distribution import distribute


def register(bot):
    @bot.message_handler(commands=["airdrop_slh"])
    def airdrop_slh(message):
        distributor_uid = str(message.from_user.id)
        if not require_permission(distributor_uid, "alpha.distribute"):
            bot.reply_to(message, "⛔️ אין לך הרשאת חלוקת SLH.")
            return

        parts = message.text.split()
        if len(parts) < 3:
            bot.reply_to(
                message,
                "שימוש: /airdrop_slh <uid> <amount> [event_id]"
            )
            return

        recipient_uid = parts[1].strip()
        amount = parts[2].strip()
        event_id = parts[3].strip() if len(parts) >= 4 else ""
        if not event_id:
            bot.reply_to(message, "❌ event_id חובה כדי למנוע חלוקה כפולה.")
            return

        try:
            result = distribute(
                distributor_uid=distributor_uid,
                recipient_uid=recipient_uid,
                amount=amount,
                reason="alpha_air",
                event_id=event_id,
            )
        except PermissionError:
            bot.reply_to(message, "⛔️ אין לך הרשאת חלוקת SLH.")
            return
        except ValueError as exc:
            bot.reply_to(message, f"❌ {exc}")
            return
        except Exception:
            bot.reply_to(message, "❌ חלוקת SLH נכשלה. לא בוצע חיוב חלקי.")
            return

        if result.get("status") == "already_completed":
            bot.reply_to(
                message,
                f"ℹ️ חלוקת AIR כבר בוצעה.\n"
                f"🪙 {result['amount']:g} SLH\n"
                f"👤 {result['to_uid']}\n"
                f"🆔 {result['event_id']}"
            )
            return

        bot.reply_to(
            message,
            f"✅ AIR הושלם\n"
            f"🪙 {result['amount']:g} SLH\n"
            f"👤 {result['to_uid']}\n"
            f"📤 From: {result['from_uid']}\n"
            f"🆔 {result['event_id']}"
        )
