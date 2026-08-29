from core.authority import is_owner
from core import economy_service

def register(bot):
    @bot.message_handler(commands=["airdrop"])
    def airdrop(m):
        if not is_owner(m):
            bot.reply_to(m, "⛔️ OWNER only")
            return
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
            result = economy_service.record_transaction(uid, amount, reason="airdrop", meta={"source":"airdrop"})
            bot.reply_to(m, f"✅ Airdrop sent: {amount} credits to {uid}")
        except Exception as e:
            bot.reply_to(m, f"❌ {e}")
