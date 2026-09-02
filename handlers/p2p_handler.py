from core import economy_service


def register(bot):

    @bot.message_handler(commands=["transfer"])
    def transfer_cmd(message):

        uid = str(message.from_user.id)
        parts = message.text.split()

        if len(parts) != 3:
            bot.reply_to(
                message,
                "📤 שימוש:\n"
                "/transfer <recipient_uid> <amount>\n\n"
                "לדוגמה:\n"
                "/transfer 5010371391 100"
            )
            return

        recipient_uid = str(parts[1]).strip()

        try:
            amount = float(parts[2])
        except (TypeError, ValueError):
            bot.reply_to(message, "❌ סכום לא תקין.")
            return

        idempotency_key = f"TG-TRANSFER-{uid}-{message.message_id}"

        try:
            result = economy_service.transfer_credits(
                sender_uid=uid,
                recipient_uid=recipient_uid,
                amount=amount,
                idempotency_key=idempotency_key,
                meta={
                    "source": "telegram",
                    "message_id": message.message_id,
                },
            )

        except ValueError as exc:
            error = str(exc)

            messages = {
                "SELF_TRANSFER": "❌ אי אפשר להעביר לעצמך.",
                "SENDER_NOT_FOUND": "❌ חשבון השולח לא נמצא.",
                "RECIPIENT_NOT_FOUND": "❌ חשבון המקבל לא נמצא.",
                "INVALID_TRANSFER_AMOUNT": "❌ סכום ההעברה חייב להיות גדול מאפס.",
                "INSUFFICIENT_CREDITS": "❌ אין מספיק Credits לביצוע ההעברה.",
                "INVALID_IDEMPOTENCY_KEY": "❌ לא ניתן ליצור מזהה העברה תקין.",
            }

            bot.reply_to(
                message,
                messages.get(error, "❌ ההעברה נכשלה.")
            )
            return

        except Exception:
            bot.reply_to(
                message,
                "❌ אירעה שגיאה פנימית. ההעברה לא בוצעה."
            )
            return

        if result.get("status") == "duplicate":
            bot.reply_to(
                message,
                "ℹ️ ההעברה כבר בוצעה.\n"
                f"Transfer ID: {result.get('transfer_id')}"
            )
            return

        bot.reply_to(
            message,
            "✅ ההעברה בוצעה בהצלחה!\n\n"
            f"📤 נשלחו: {result.get('amount')} Credits\n"
            f"👤 למשתמש: {result.get('recipient_uid')}\n"
            f"💰 היתרה שלך: {result.get('sender_balance')} Credits\n"
            f"🧾 Transfer ID: {result.get('transfer_id')}"
        )


    print("✅ p2p handler loaded")
