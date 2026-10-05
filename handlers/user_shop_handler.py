import math
import re
from datetime import datetime, timezone

import state_manager


def _slugify(value):
    value = re.sub(r"[^\w\s-]", "", str(value or ""), flags=re.UNICODE).strip().lower()
    value = re.sub(r"[-\s]+", "_", value)
    return value[:60] or "item"


def register(bot):
    @bot.message_handler(commands=["sell"])
    def sell_cmd(message):
        uid = str(message.from_user.id)
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(message, "שימוש: /sell שם המוצר | מחיר ב-Credits | כמות")
            return
        fields = [part.strip() for part in parts[1].split("|")]
        if len(fields) != 3 or not fields[0]:
            bot.reply_to(message, "שימוש: /sell שם המוצר | מחיר ב-Credits | כמות")
            return
        name = fields[0]
        try:
            price = float(fields[1])
            stock = int(fields[2])
        except (TypeError, ValueError):
            bot.reply_to(message, "❌ מחיר חייב להיות מספר וכמות חייבת להיות מספר שלם.")
            return
        if not math.isfinite(price) or price <= 0 or stock <= 0:
            bot.reply_to(message, "❌ המחיר והכמות חייבים להיות גדולים מאפס.")
            return

        item_id = "u_" + uid + "_" + _slugify(name)
        now = datetime.now(timezone.utc).isoformat()

        def mutate(db):
            products = db.setdefault("products", {})
            if item_id in products:
                return None, "ITEM_ID_EXISTS"
            products[item_id] = {
                "name": name,
                "price": price,
                "type": "physical",
                "inventory": stock,
                "seller_uid": uid,
                "listed_at": now,
            }
            return item_id, None

        created_id, error = state_manager.atomic_update(mutate)
        if error:
            bot.reply_to(message, f"❌ לא ניתן לפרסם: {error}")
            return
        bot.reply_to(
            message,
            f"✅ המוצר פורסם בשוק.\n🆔 {created_id}\n💰 מחיר: {price:g} Credits\n📦 מלאי: {stock}\n💸 תקבול מוכר: 90% בכל מכירה\n🏦 עמלת SLH: 10%",
        )

    @bot.message_handler(commands=["my_products"])
    def my_products_cmd(message):
        uid = str(message.from_user.id)
        db = state_manager.load_db()
        products = db.get("products") or {}
        owned = [(item_id, p) for item_id, p in products.items()
                 if isinstance(p, dict) and p.get("type") == "physical" and str(p.get("seller_uid")) == uid]
        if not owned:
            bot.reply_to(message, "📦 אין לך כרגע מוצרים פיזיים פעילים.")
            return
        lines = ["📦 *המוצרים שלי*"]
        for item_id, product in owned:
            lines.append(
                f"*{product.get('name', item_id)}*\n"
                f"🆔 {item_id}\n"
                f"💰 {product.get('price')} Credits\n"
                f"📦 מלאי: {int(product.get('inventory', 0) or 0)}"
            )
        bot.reply_to(message, "\n\n".join(lines), parse_mode="Markdown")

    @bot.message_handler(commands=["umarket"])
    def user_market_cmd(message):
        db = state_manager.load_db()
        products = db.get("products") or {}
        listed = [(item_id, p) for item_id, p in products.items()
                  if isinstance(p, dict) and p.get("type") == "physical"
                  and int(p.get("inventory", 0) or 0) > 0
                  and float(p.get("price", 0) or 0) > 0]
        if not listed:
            bot.reply_to(message, "🏪 השוק הפיזי ריק כרגע.")
            return
        lines = ["🏪 *SLH User Marketplace*", ""]
        for item_id, product in listed:
            lines.append(
                f"*{product.get('name', item_id)}* — {product.get('price')} Credits\n"
                f"📦 מלאי: {int(product.get('inventory', 0) or 0)}\n"
                f"/buy {item_id}\n"
            )
        bot.reply_to(message, "\n".join(lines).strip(), parse_mode="Markdown")

    @bot.message_handler(commands=["unsell"])
    def unsell_cmd(message):
        uid = str(message.from_user.id)
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(message, "שימוש: /unsell item_id")
            return
        item_id = parts[1].strip()

        def mutate(db):
            products = db.setdefault("products", {})
            product = products.get(item_id)
            if not product:
                return False, "PRODUCT_NOT_FOUND"
            if product.get("type") != "physical":
                return False, "NOT_PHYSICAL_PRODUCT"
            if str(product.get("seller_uid")) != uid:
                return False, "NOT_OWNER"
            products.pop(item_id, None)
            return True, None

        ok, error = state_manager.atomic_update(mutate)
        if not ok:
            bot.reply_to(message, f"❌ לא ניתן להסיר: {error}")
            return
        bot.reply_to(message, "✅ המוצר הוסר מהשוק.")
