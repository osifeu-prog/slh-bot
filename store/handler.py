"""SLH Store Handler - רק 2 פקודות"""
from.engine import format_shop_message, buy_item

def handle_shop(message, user_id, get_balance_func):
    """מטפל ב /shop"""
    balance = get_balance_func(user_id)
    return format_shop_message(balance)

def handle_buy(message, user_id, get_balance_func, spend_func):
    """מטפל ב /buy item_id"""
    parts = message.split()
    if len(parts) < 2:
        return "שימוש: /buy item_id\nדוגמה: /buy role_vip"

    item_id = parts[1]
    success, response = buy_item(user_id, item_id, get_balance_func, spend_func)
    return response
