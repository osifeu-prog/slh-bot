"""SLH Store Engine - מבודד לחלוטין"""
import json, os

ITEMS_FILE = os.path.join(os.path.dirname(__file__), "items.json")

def load_items():
    """טוען את המוצרים מהקובץ"""
    try:
        with open(ITEMS_FILE, 'r', encoding='utf-8-sig') as f:
            return json.load(f)
    except:
        return {}

def format_shop_message(user_balance=0):
    """מחזיר הודעת חנות מעוצבת"""
    items = load_items()
    msg = "🏪 *חנות SLH EMPIRE*\n\n"

    for item_id, data in items.items():
        price_text = "חינם" if data['price'] == 0 else f"{data['price']} SLH"
        msg += f"*{data['name']}* - {price_text}\n"
        msg += f"`/buy {item_id}`\n\n"

    msg += f"💰 היתרה שלך: {user_balance} SLH"
    return msg

def buy_item(user_id, item_id, get_balance_func, spend_func):
    """פונקציית קנייה. מקבלת את הפונקציות של economy_bridge"""
    items = load_items()
    if item_id not in items:
        return False, "פריט לא נמצא"

    item = items[item_id]
    balance = get_balance_func(user_id)

    if balance < item['price']:
        return False, f"אין מספיק SLH. צריך {item['price']}"

    success = spend_func(user_id, item['price'], f"Buy: {item['name']}")
    if not success:
        return False, "שגיאה בחיוב"

    return True, f"✅ נקנה: {item['name']}\nיתרה חדשה: {balance - item['price']} SLH"
