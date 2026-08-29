import json
from pathlib import Path

def register(bot):
    @bot.message_handler(commands=["ton_address"])
    def ton_address_cmd(msg):
        db = json.loads(Path("state/db.json").read_text(encoding="utf-8"))
        ton = db.get("ton_settings", {})
        addr = ton.get("wallet", "לא הוגדר")
        bot.reply_to(msg, f"💎 כתובת TON להפקדות:\n{addr}\n\nהפקד USDT או TON ושלח /claim עם tx hash.")
