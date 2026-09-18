"""SLH Store Engine - catalog + inventory display"""
import json
from pathlib import Path

ITEMS_FILE = Path(__file__).resolve().parent / "items.json"
DB_PATH = Path("state/db.json")

# Items with a dedicated Telegram Stars checkout path.
STARS_ITEMS = set()


def load_items():
    try:
        return json.loads(ITEMS_FILE.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def load_products():
    try:
        db = json.loads(DB_PATH.read_text(encoding="utf-8"))
        return db.get("products", {})
    except Exception:
        return {}


def format_shop_message(user_balance=0):
    items = load_items()
    products = load_products()
    stars_items = {item_id for item_id, data in items.items() if isinstance(data, dict) and int(data.get("price_stars", 0) or 0) > 0}

    msg = "🏪 *חנות SLH EMPIRE*\n\n"
    msg += "⭐ לרכישות הנתמכות ב-Telegram Stars השתמש ב-/buystars.\n"
    msg += "💎 /buy נשאר מסלול רכישה פנימי ב-Credits עבור פריטים שתומכים בו.\n\n"

    for item_id, data in items.items():
        price = data.get("price", 0)
        if item_id in stars_items:
            price_text = f"{price} Stars"
        else:
            price_text = "חינם" if price == 0 else f"{price} Credits"

        inventory = None
        product = products.get(item_id)
        if product:
            inventory = product.get("inventory")

        inv_text = ""
        if inventory is not None:
            inv_text = f" | במלאי: {int(inventory)}"

        msg += f"*{data.get('name', item_id)}* - {price_text}{inv_text}\n"
        if item_id in stars_items:
            msg += f"/buystars {item_id} — ⭐ Telegram Stars\n"
        else:
            msg += f"/buy {item_id} — Credits\n"
        msg += "\n"

    msg += "⭐ VIP חודשי — 499 Telegram Stars\n/vip — מנוי מתחדש חודשי\n\n"
    msg += f"💰 היתרה שלך: {user_balance} Credits"
    return msg


def buy_item(user_id, item_id, get_balance_func, spend_func):
    items = load_items()
    if item_id not in items:
        return False, "פריט לא נמצא"

    item = items[item_id]
    price = item.get("price", 0)
    balance = get_balance_func(user_id)

    if balance < price:
        return False, f"אין מספיק Credits. צריך {price}"

    success = spend_func(user_id, price, f"Buy: {item.get('name')}")
    if not success:
        return False, "שגיאה בחיוב"

    return True, f"✅ נקנה: {item.get('name')}\nיתרה חדשה: {balance - price} Credits"
