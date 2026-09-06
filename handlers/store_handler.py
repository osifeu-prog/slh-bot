"""SLH Store Handler"""
from store.engine import format_shop_message
from store.purchase_service import purchase
from core.economy_bridge import get_balance


def register(bot):
    @bot.message_handler(commands=["shop"])
    def shop_cmd(message):
        uid = message.from_user.id
        bal = get_balance(uid)
        bot.reply_to(message, format_shop_message(bal), parse_mode="Markdown")

    @bot.message_handler(commands=["buy"])
    def buy_cmd(message):
        uid = message.from_user.id
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(message, "שימוש: /buy item_id")
            return

        item_id = parts[1].strip()
        chat_id = getattr(getattr(message, "chat", None), "id", "unknown")
        message_id = getattr(message, "message_id", "unknown")
        request_id = f"chat:{chat_id}:message:{message_id}:item:{item_id}"
        ok, result = purchase(uid, item_id, request_id=request_id)
        if not ok:
            bot.reply_to(message, f"❌ הרכישה נכשלה: {result}")
            return

        status = result.get("status", "completed")
        if status == "pending_fulfillment":
            text = f"🟡 ההזמנה התקבלה: {result['item']}\n💰 שולם: {result['amount']} SLH\n⏳ ההקצאה הפיזית ממתינה להשלמה."
        else:
            text = f"✅ נרכש: {result['item']}\n💰 שולם: {result['amount']} SLH"
        bot.reply_to(message, text, parse_mode="Markdown")
