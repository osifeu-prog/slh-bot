"""SLH Shop — AI course, VIP, WhatsApp bot paid in ILS/TON."""
from datetime import datetime, timezone
import state_manager
from store.grant_engine import apply_grant

CATALOG = {
    "ai_course": {"name": "קורס AI Automation", "price_ils": 499, "price_ton": 15, "grant": {"digital": "ai_course"}},
    "vip_monthly": {"name": "מנוי VIP חודשי", "price_ils": 199, "price_ton": 5, "grant": {"permission": "vip_access"}},
    "whatsapp_bot": {"name": "בוט וואטסאפ מוכן", "price_ils": 349, "price_ton": 10, "grant": {"digital": "whatsapp_bot"}},
}
PAY_TEXT = "Bit / TON / העברה — אחרי התשלום שלח /paid_shop <order_id>"
K = "shop_orders"


def _now(): return datetime.now(timezone.utc).isoformat()


def _create(uid, item, oid):
    def mut(db):
        o = db.setdefault(K, {})
        if oid in o: return o[oid]
        o[oid] = {
            "order_id": oid, "uid": str(uid), "item_id": item,
            "item_name": CATALOG[item]["name"],
            "price_ils": CATALOG[item]["price_ils"],
            "price_ton": CATALOG[item]["price_ton"],
            "status": "AWAITING_PAYMENT", "created_at": _now(),
        }
        return o[oid]
    return state_manager.atomic_update(mut)


def _set(oid, st, **ex):
    def mut(db):
        o = db.setdefault(K, {}).get(oid)
        if not o: raise KeyError("ORDER_NOT_FOUND")
        o["status"] = st; o.update(ex); return o
    return state_manager.atomic_update(mut)


def register(bot, context=None):
    @bot.message_handler(commands=["shop"])
    def shop_cmd(m):
        lines = ["🛒 SLH Shop\n"]
        for k, v in CATALOG.items():
            lines.append(f"{v['name']}\n  /buy_shop {k}  —  ₪{v['price_ils']} / {v['price_ton']} TON\n")
        bot.reply_to(m, "\n".join(lines))

    @bot.message_handler(commands=["buy_shop"])
    def buy_shop(m):
        p = (m.text or "").split(maxsplit=1)
        if len(p) < 2 or p[1].strip() not in CATALOG:
            bot.reply_to(m, "שימוש: /buy_shop <ai_course|vip_monthly|whatsapp_bot>")
            return
        item = p[1].strip()
        oid = "SHOP-%s-%s" % (m.from_user.id, m.message_id)
        o = _create(m.from_user.id, item, oid)
        bot.reply_to(m, "הזמנה %s\n%s\nלתשלום: ₪%s או %s TON\n\n%s" % (
            oid, o["item_name"], o["price_ils"], o["price_ton"], PAY_TEXT))

    @bot.message_handler(commands=["paid_shop"])
    def paid_shop(m):
        p = (m.text or "").split(maxsplit=1)
        if len(p) < 2: bot.reply_to(m, "שימוש: /paid_shop <order_id>"); return
        try: o = _set(p[1].strip(), "PAYMENT_CLAIMED")
        except KeyError: bot.reply_to(m, "הזמנה לא נמצאה"); return
        bot.reply_to(m, "התקבל. ממתין לאישור.")
        try:
            from core.identity import OWNER_TELEGRAM_ID
            bot.send_message(OWNER_TELEGRAM_ID, "תשלום חנות: %s | %s | %s | uid=%s" % (
                o["order_id"], o["item_name"], o["price_ils"], o["uid"]))
        except Exception as e: print("[SHOP] notify fail", type(e).name)

    @bot.message_handler(commands=["shop_pending"])
    def shop_pending(m):
        from admin_utils import is_admin
        if not is_admin(m): bot.reply_to(m, "Admin only"); return
        db = state_manager.load_db()
        rows = ["%s | %s | %s | %s" % (o["order_id"], o["status"], o["item_name"], o["uid"])
                for o in db.get(K, {}).values() if o["status"] in ("AWAITING_PAYMENT", "PAYMENT_CLAIMED")]
        bot.reply_to(m, "\n".join(rows) if rows else "אין הזמנות פתוחות")