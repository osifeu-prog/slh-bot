"""SLH Store Handler"""
from store.engine import format_shop_message
from store.purchase_service import purchase
from core.economy_bridge import get_balance


def register(bot):
    @bot.message_handler(commands=['shop'])
    def shop_cmd(message):
        uid = str(message.from_user.id)
        bal = get_balance(uid)
        bot.reply_to(message, format_shop_message(bal))

    @bot.message_handler(commands=['buy'])
    def buy_cmd(message):
        uid = str(message.from_user.id)
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(message, "שימוש: /buy item_id")
            return
        item_id = parts[1].strip()
        request_id = f"telegram_buy:{message.chat.id}:{message.message_id}"
        ok, result = purchase(uid, item_id, request_id=request_id)

        if ok:
            status = result.get("status")
            if status == "ALREADY_COMPLETED":
                text = f"ℹ️ הרכישה כבר הושלמה: {result['item']}\n💰 שולם: {result['paid']} Credits"
            else:
                text = f"✅ נרכש: {result['item']}\n💰 שולם: {result['paid']} Credits"
            cashback = result.get("cashback") or {}
            if cashback.get("status") == "APPLIED":
                text += f"\n🎁 החזר WhatsApp: {cashback.get('credits')} Credits"
            elif cashback.get("status") == "PENDING":
                text += "\n⏳ הרכישה הושלמה; החזר הנאמנות ממתין להתאמה אוטומטית."
        elif result == "RECOVERABLE":
            text = "⚠️ התשלום נשמר והרכישה דורשת השלמת אספקה. ניסיון חוזר לא יחייב שוב."
        elif result == "IN_PROGRESS":
            text = "⏳ הרכישה כבר נמצאת בתהליך אספקה. אין לבצע חיוב נוסף."
        else:
            text = result
        bot.reply_to(message, text, parse_mode="Markdown")
