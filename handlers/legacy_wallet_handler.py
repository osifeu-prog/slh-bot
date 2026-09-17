from core.wallet_binding import issue_challenge, verify_signature
from core.legacy_wallet_migration import record_legacy_claim


def register(bot):
    @bot.message_handler(commands=["migrate"])
    def migrate(msg):
        parts = msg.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(msg, "שימוש: /migrate <legacy_bnb_wallet>")
            return

        address = parts[1].strip()
        try:
            challenge = issue_challenge(str(msg.from_user.id), address)
        except ValueError as exc:
            bot.reply_to(msg, f"❌ {exc}")
            return

        bot.reply_to(
            msg,
            "🔗 חיבור ארנק SLH ישן\n\n"
            "חתום בארנק הישן על ההודעה הבאה. החתימה מוכיחה בעלות בלבד; היא "
            "אינה מאשרת העברת כספים.\n\n"
            f"{challenge['message']}\n\n"
            "לאחר החתימה שלח:\n"
            "/migrate_verify <wallet> <signature>",
        )

    @bot.message_handler(commands=["migrate_verify"])
    def migrate_verify(msg):
        parts = msg.text.split(maxsplit=2)
        if len(parts) < 3:
            bot.reply_to(msg, "שימוש: /migrate_verify <wallet> <signature>")
            return

        address = parts[1].strip()
        signature = parts[2].strip()
        uid = str(msg.from_user.id)

        try:
            binding = verify_signature(uid, address, signature)
            result = record_legacy_claim(uid, address, 0)
        except ValueError as exc:
            bot.reply_to(msg, f"❌ {exc}")
            return

        status = result.get("status")
        suffix = " (החיבור כבר היה קיים)" if status == "duplicate" else ""
        bot.reply_to(
            msg,
            "✅ ארנק SLH הישן חובר למערכת החדשה%s\n\n"
            "הארנק נשאר בשליטתך. לא הועברו טוקנים ולא נשמר מפתח פרטי.\n"
            f"כתובת: {binding.get('address', address)}\n"
            "מהשלב הזה אפשר להשתמש בארנק המאומת במסלולי ה־BNB של SLH OS."
            % suffix,
        )

    print("legacy_wallet_handler loaded")
