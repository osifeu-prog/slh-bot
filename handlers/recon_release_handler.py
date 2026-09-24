"""/recon_release <order_id> [apply] — OWNER only.
Without 'apply' it only shows what would be restored (dry run)."""
from core.authority import is_owner
from core.missed_release_correction import correct_missed_release


def register(bot, context=None):
    @bot.message_handler(commands=["recon_release"])
    def recon_release(msg):
        if not is_owner(msg.from_user.id):
            bot.reply_to(msg, "⛔ OWNER only")
            return
        parts = msg.text.split()
        if len(parts) not in (2, 3) or (len(parts) == 3 and parts[2] != "apply"):
            bot.reply_to(msg, "שימוש: /recon_release <order_id> [apply]")
            return
        try:
            r = correct_missed_release(parts[1], msg.from_user.id, apply=len(parts) == 3,
                                       note="RECON-MISSED-RELEASE-20260924")
        except ValueError as e:
            bot.reply_to(msg, f"❌ {e}")
            return
        bot.reply_to(msg, "\n".join(f"{k}: {v}" for k, v in r.items()))
