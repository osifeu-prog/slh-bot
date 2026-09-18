"""Stars checkout for the SLH store."""
from telebot.types import LabeledPrice
from store.engine import load_items
from store.stars_purchase_service import get_stars_items, get_stars_price


def register(bot):
    @bot.message_handler(commands=['buystars'])
    def buystars(m):
        parts = m.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(m, "שימוש: /buystars <item_id>\nזמין ב-Stars: " + ", ".join(get_stars_items()))
            return

        item_id = parts[1].strip()
        items = load_items()
        item = items.get(item_id)
        if not isinstance(item, dict):
            bot.reply_to(m, "❌ המוצר לא נמצא")
            return

        stars = get_stars_price(item_id)
        if stars is None:
            bot.reply_to(m, "❌ המוצר אינו זמין לרכישה ב-Stars")
            return

        name = item.get("name", item_id)
        try:
            bot.send_invoice(
                chat_id=m.chat.id,
                title=name,
                description="SLH Store - " + name,
                invoice_payload="item_" + item_id + "_" + str(m.from_user.id),
                provider_token="",
                currency="XTR",
                prices=[LabeledPrice(label=name, amount=stars)],
                start_parameter="item",
                is_flexible=False,
            )
        except Exception as e:
            bot.reply_to(m, "❌ יצירת חשבונית נכשלה. נסה שוב מאוחר יותר.")
            print(f"[STARS_STORE] invoice error: {type(e).__name__}")
