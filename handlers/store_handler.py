"""SLH Store Handler"""
from store.engine import format_shop_message
from store.purchase_service import purchase
from core.economy_bridge import get_balance, spend

def register(bot):
    @bot.message_handler(commands=['shop'])
    def shop_cmd(message):
        uid = message.from_user.id
        bal = get_balance(uid)
        msg = format_shop_message(bal)
        bot.reply_to(message, msg, parse_mode="Markdown")

    @bot.message_handler(commands=['buy'])
    def buy_cmd(message):
        uid = message.from_user.id
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(message, "שימוש: /buy item_id")
            return
        item_id = parts[1]
        ok, result = purchase(uid, item_id)

        if ok:
            text = f"✅ נרכש: {result['item']}\n💰 שולם: {result['paid']} SLH"
        else:
            text = result
        bot.reply_to(message, text, parse_mode="Markdown")
