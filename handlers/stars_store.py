"""Stars checkout for the SLH store."""
import json
from pathlib import Path
from telebot.types import LabeledPrice

ITEMS_FILE = Path("store/items.json")
STARS_PER_ITEM = {
    "esp32_pro": 888,
    "esp32_standard": 444,
    "role_vip": 500,
    "bot_signal": 1000,
}

def _items():
    try:
        return json.loads(ITEMS_FILE.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}

def register(bot):
    @bot.message_handler(commands=['buystars'])
    def buystars(m):
        parts = m.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(m, "usage: /buystars <item_id>\navailable: " + ", ".join(STARS_PER_ITEM))
            return
        item_id = parts[1].strip()
        items = _items()
        if item_id not in items:
            bot.reply_to(m, "ITEMNOTFOUND")
            return
        stars = STARS_PER_ITEM.get(item_id)
        if not stars:
            bot.reply_to(m, "item not available for Stars")
            return
        name = items[item_id].get("name", item_id)
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
            bot.reply_to(m, "invoice failed: " + str(e))
