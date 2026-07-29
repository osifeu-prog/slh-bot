import json
class ShopPlugin:
    def __init__(self):
        self.items_file = "store/items.json"
    
    def list_items(self):
        return json.load(open(self.items_file))
    
    def buy(self, user_id, item_id, db):
        items = self.list_items()
        if item_id not in items: return "❌ פריט לא קיים"
        price = items[item_id]["price"]
        if db["users"][user_id]["credits"] < price: return "❌ אין מספיק SLH"
        db["users"][user_id]["credits"] -= price
        return f"✅ קנית: {items[item_id]['name']}"
