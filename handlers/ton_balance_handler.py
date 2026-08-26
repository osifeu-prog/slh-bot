import json
from pathlib import Path
from core.ton_lab import get_ton_balance

def register(bot):
    @bot.message_handler(commands=["ton_balance"])
    def ton_balance_cmd(msg):
        db=json.loads(Path("state/db.json").read_text(encoding="utf-8"))
        wallet=db.get("ton_settings",{}).get("wallet")
        if not wallet:
            bot.reply_to(msg, "❌ TON wallet not configured")
            return
        bal=get_ton_balance(wallet)
        bot.reply_to(msg, f"💎 TON Wallet: {wallet}\n💰 Balance: {bal} TON")
