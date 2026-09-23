"""Telegram Mini App command bridge.

Only allowlisted, user-scoped exchange actions are accepted from
Telegram.WebApp.sendData(). Arbitrary bot commands are never executed.
"""
import json
from decimal import Decimal
import state_manager

ALLOWED_COMMANDS = {"/wallet","/pay","/shop","/orders","/courses","/academy","/share","/staking","/positions","/buy","/buystars","/order_esp32","/buy_shop","/ask"}


def _payload(raw):
    raw = (raw or "").strip()
    if not raw:
        return {}
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {"cmd": str(value)}
    except (TypeError, ValueError):
        return {"cmd": raw}


def register(bot, context=None):
    @bot.message_handler(content_types=["web_app_data"])
    def webapp_data(message):
        data = _payload(getattr(message.web_app_data, "data", ""))
        cmd = str(data.get("cmd", "")).strip()
        if not cmd:
            bot.send_message(message.chat.id, "❌ פעולה ריקה")
            return

        parts = cmd.split()
        action = parts[0].lstrip("/").lower()
        uid = str(message.from_user.id)
        chat_id = message.chat.id

        try:
            if action in ("buy_slh", "sell_slh") and len(parts) == 3:
                _exchange_order(bot, chat_id, uid, action, parts[1], parts[2])
            elif action == "orders" and len(parts) == 1:
                _orders(bot, chat_id, uid)
            elif action == "cancel" and len(parts) == 2:
                _cancel(bot, chat_id, uid, parts[1])
            elif action == "transfer" and len(parts) == 3:
                _transfer(bot, chat_id, uid, parts[1], parts[2], message.message_id)
            elif action == "shop" and len(parts) == 1:
                _shop(bot, chat_id)
            elif action in {x.lstrip("/") for x in ALLOWED_COMMANDS} and len(parts) <= 3:
                message.text = cmd
                message.content_type = "text"
                bot.process_new_messages([message])
            else:
                bot.send_message(chat_id, "❌ פעולה זו אינה זמינה מה־Mini App")
        except Exception as exc:
            print("[WEBAPP_DATA] error:", type(exc).__name__, str(exc)[:160])
            bot.send_message(chat_id, "❌ הפעולה נכשלה: " + str(exc)[:160])


def _exchange_order(bot, chat_id, uid, action, amount_text, price_text):
    from handlers.exchange_handler import _dec, _place

    amount = _dec(amount_text, "amount")
    price = _dec(price_text, "price")
    side = "buy" if action == "buy_slh" else "sell"

    # One logical Mini App action gets one idempotency key.
    request_id = f"WEBAPP-EXCHANGE-{uid}-{side}-{amount_text}-{price_text}"

    def mutate(db):
        requests = db.setdefault("exchange_requests", {})
        existing = requests.get(request_id)
        if existing is not None:
            return existing
        return _place(db, uid, side, amount, price, request_id)

    result = state_manager.atomic_update(mutate)
    bot.send_message(
        chat_id,
        "✅ " + ("BUY" if side == "buy" else "SELL") +
        f" #{result['order_id']}\n"
        f"בוצע: {result['filled']} SLH\n"
        f"פתוח: {result['remaining']} SLH\n"
        f"סטטוס: {result['status']}"
    )


def _transfer(bot, chat_id, uid, recipient_uid, amount_text, message_id):
    from core import economy_service

    try:
        amount = float(amount_text)
    except (TypeError, ValueError):
        raise ValueError("INVALID_TRANSFER_AMOUNT")

    result = economy_service.transfer_credits(
        sender_uid=uid,
        recipient_uid=str(recipient_uid),
        amount=amount,
        idempotency_key=f"WEBAPP-TRANSFER-{uid}-{message_id}",
        meta={"source": "telegram_webapp", "message_id": message_id},
    )
    if result.get("status") == "duplicate":
        bot.send_message(chat_id, f"ℹ️ ההעברה כבר בוצעה. Transfer ID: {result.get('transfer_id')}")
        return
    bot.send_message(
        chat_id,
        "✅ ההעברה בוצעה\n"
        f"📤 {result.get('amount')} Credits\n"
        f"👤 למשתמש: {result.get('recipient_uid')}\n"
        f"💰 יתרה: {result.get('sender_balance')} Credits\n"
        f"🧾 {result.get('transfer_id')}"
    )


def _orders(bot, chat_id, uid):
    db = state_manager.load_db()
    orders = [
        o for o in db.get("exchange_orders", {}).values()
        if str(o.get("uid")) == uid and o.get("status") == "open"
    ]
    orders.sort(key=lambda o: int(o.get("sequence", 0)))
    if not orders:
        bot.send_message(chat_id, "📋 אין לך הוראות פתוחות")
        return

    lines = ["📋 ההוראות הפתוחות שלך:"]
    for o in orders[:30]:
        lines.append(
            f"{o.get('id')} | {o.get('side')} | "
            f"{o.get('remaining_amount')} SLH @ {o.get('limit_price')} C"
        )
    bot.send_message(chat_id, "\n".join(lines))


def _cancel(bot, chat_id, uid, order_id):
    from handlers.exchange_handler import cancel_order_in_db

    state_manager.atomic_update(
        lambda db: cancel_order_in_db(db, uid, order_id)
    )
    bot.send_message(chat_id, f"✅ הוראה #{order_id} בוטלה")


def _shop(bot, chat_id):
    bot.send_message(
        chat_id,
        "🛒 SLH Shop\n"
        "/buy_shop ai_course — ₪499\n"
        "/buy_shop vip_monthly — ₪199\n"
        "/buy_shop whatsapp_bot — ₪349"
    )


print("webapp_data_handler loaded")
