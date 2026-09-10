"""SLH Store Handler"""
from store.engine import format_shop_message
from store.purchase_service import purchase
from core.economy_bridge import get_balance

# Hardware sales are temporarily blocked until the hardware grant path is atomic.
# See: store/grant_engine.py (hardware branch) + core/esp_license.py
HARDWARE_ITEMS = {"esp32_pro", "esp32_standard"}


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
        item_id = parts[1].strip()

        if item_id in HARDWARE_ITEMS:
            bot.reply_to(
                message,
                "🚧 רכישת חומרה מושהית זמנית.\n"
                "לטעינת קרדיטים: /pay"
            )
            return

        # Telegram message identity is stable across retries, so the same
        # command cannot create a fresh purchase key and charge twice.
        request_id = f"tg:{message.chat.id}:{message.message_id}"
        ok, result = purchase(uid, item_id, request_id=request_id)

        if ok:
            item_name = result.get("item", item_id)
            amount = result.get("amount", 0)
            status = result.get("status")
            if status == "pending_fulfillment":
                text = f"✅ תשלום התקבל: {item_name}\n💰 שולם: {amount:g} SLH\n⏳ המימוש בטיפול."
            else:
                text = f"✅ נרכש: {item_name}\n💰 שולם: {amount:g} SLH"
        else:
            text = result
        bot.reply_to(message, text, parse_mode="Markdown")
