from core import mint_authority


def register(bot):
    @bot.message_handler(commands=["airdrop"])
    def airdrop(m):
        parts = m.text.split()
        if len(parts) < 3:
            bot.reply_to(m, "Usage: /airdrop <uid> <amount>")
            return

        uid = parts[1]
        try:
            amount = float(parts[2])
        except ValueError:
            bot.reply_to(m, "Invalid amount")
            return

        try:
            mint_authority.mint_credits(
                issuer_uid=m,
                recipient_uid=uid,
                amount=amount,
                reason="airdrop",
                meta={"source": "airdrop"},
            )
            bot.reply_to(m, f"✅ Airdrop sent: {amount} credits to {uid}")
        except PermissionError:
            bot.reply_to(m, "⛔️ OWNER only")
        except Exception as e:
            bot.reply_to(m, f"❌ {e}")
