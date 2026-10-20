"""Stars checkout for the SLH store."""
from telebot.types import LabeledPrice
from store.engine import load_items, resolve_item_id
from store.stars_purchase_service import get_stars_items, get_stars_price
from core.stars_price_authority import TELEGRAM_STARS_CURRENCY
from core.stars_gate import (
    store_stars_item_allowed,
    store_stars_item_sales_open,
    store_stars_sales_open,
)


def register(bot):
    @bot.message_handler(commands=['buystars'])
    def buystars(m):
        parts = (m.text or "").split(maxsplit=1)
        if len(parts) < 2:
            if not store_stars_sales_open():
                bot.reply_to(m, "⛔ מכירות החנות ב-Stars סגורות כרגע. לא נוצרה חשבונית חדשה.")
                return
            available = [
                item_id for item_id in get_stars_items()
                if store_stars_item_allowed(item_id)
            ]
            if not available:
                bot.reply_to(m, "⛔ אין כרגע מוצרי Stars שאושרו למכירה.")
                return
            bot.reply_to(
                m,
                "שימוש: /buystars <item_id>\nזמין כרגע ב-Stars: " + ", ".join(available),
            )
            return

        items = load_items()
        item_id = resolve_item_id(parts[1].strip(), items)
        item = items.get(item_id) if item_id else None
        if not isinstance(item, dict):
            bot.reply_to(m, "❌ המוצר לא נמצא")
            return

        stars = get_stars_price(item_id)
        if stars is None:
            bot.reply_to(m, "❌ המוצר אינו זמין לרכישה ב-Stars")
            return

        if not store_stars_item_sales_open(item_id):
            if not store_stars_sales_open():
                bot.reply_to(m, "⛔ מכירות החנות ב-Stars סגורות כרגע. לא נוצרה חשבונית חדשה.")
            else:
                bot.reply_to(m, "⛔ המוצר הזה עדיין אינו מאושר לרכישה ב-Stars עד לאימות האספקה.")
            return

        name = item.get("name", item_id)
        try:
            bot.send_invoice(
                chat_id=m.chat.id,
                title=name,
                description="SLH Store - " + name,
                invoice_payload="item_" + item_id + "_" + str(m.from_user.id),
                provider_token="",
                currency=TELEGRAM_STARS_CURRENCY,
                prices=[LabeledPrice(label=name, amount=stars)],
                start_parameter="item",
                is_flexible=False,
            )
        except Exception as e:
            bot.reply_to(m, "❌ יצירת חשבונית נכשלה. נסה שוב מאוחר יותר.")
            print(f"[STARS_STORE] invoice error: {type(e).__name__}")
