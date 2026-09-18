"""Receives commands from Telegram Mini App via tg.sendData()."""
import json
import state_manager


def register(bot, context=None):
    @bot.message_handler(content_types=["web_app_data"])
    def webapp_data(m):
        raw = (m.web_app_data.data or "").strip()
        uid = str(m.from_user.id)
        chat_id = m.chat.id
        try:
            payload = json.loads(raw)
            cmd = str(payload.get("cmd", "")).strip()
        except (ValueError, TypeError):
            cmd = raw
        if not cmd:
            bot.send_message(chat_id, "❌ פקודה ריקה")
            return
        parts = cmd.split()
        head = parts[0].lstrip("/")
        try:
            if head in ("sell_slh", "buy_slh") and len(parts) == 3:
                _exchange(bot, chat_id, uid, head, parts[1], parts[2])
            elif head == "orders":
                _orders(bot, chat_id, uid)
            elif head == "shop":
                _shop(bot, chat_id)
            else:
                bot.send_message(chat_id, "❌ פקודה לא נתמכת: " + head)
        except Exception as e:
            bot.send_message(chat_id, "❌ שגיאה: " + str(e))
            print("[WEBAPP_DATA] error: " + str(e))


def _exchange(bot, chat_id, uid, side, amount_s, price_s):
    from handlers.exchange_handler import _place, _dec
    try:
        amount = _dec(amount_s, "amount")
        price = _dec(price_s, "price")
    except ValueError as e:
        bot.send_message(chat_id, "❌ " + str(e))
        return
    key = "webapp:" + uid + ":" + side + ":" + amount_s + ":" + price_s

    def mut(db):
        old = db.setdefault("exchange_requests", {}).get(key)
        if old is not None:
            return old
        return _place(db, uid, side, amount, price, key)
    r = state_manager.atomic_update(mut)
    bot.send_message(chat_id,
                     "✅ " + side.upper() + " #" + r["order_id"] + "\n"
                     "בוצע: " + r["filled"] + "\n"
                     "פתוח: " + r["remaining"] + " SLH\n"
                     "סטטוס: " + r["status"])


def _orders(bot, chat_id, uid):
    db = state_manager.load_db()
    rows = [o for o in db.get("exchange_orders", {}).values()
            if str(o.get("uid")) == uid and o.get("status") == "open"]
    if not rows:
        bot.send_message(chat_id, "אין הזמנות פתוחות")
        return
    lines = ["📋 הזמנות פתוחות:"]
    for o in rows:
        lines.append(o["id"] + " | " + o["side"] + " | " +
                     o["remaining_amount"] + " @ " + o["limit_price"])
    bot.send_message(chat_id, "\n".join(lines))


def _shop(bot, chat_id):
    bot.send_message(chat_id,
                     "🛒 SLH Shop\n"
                     "/buy_shop ai_course — ₪499\n"
                     "/buy_shop vip_monthly — ₪199\n"
                     "/buy_shop whatsapp_bot — ₪349")


print("webapp_data_handler loaded")
