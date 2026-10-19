import json
import os
import urllib.parse
import urllib.request

import state_manager
from core import stars_payment_authority
from core.stars_price_authority import (
    CREDIT_PACKS_BY_ID,
    TELEGRAM_STARS_CURRENCY,
    VIP_MONTHLY_STARS,
    VIP_SUBSCRIPTION_PERIOD,
    resolve_credit_pack,
)
from store.stars_purchase_service import get_stars_price, purchase_item_with_stars
from telebot.types import LabeledPrice, PreCheckoutQuery, InlineKeyboardMarkup, InlineKeyboardButton

PROVIDER_TOKEN = ""

STARS_PACKS = CREDIT_PACKS_BY_ID


def _resolve_stars_package(credits, stars_paid):
    package = resolve_credit_pack(credits, stars_paid)
    if package is None:
        return None
    return package.pack_id, package.stars, package.credits, package.label


def _create_vip_invoice_link(bot, uid):
    """Create a recurring Telegram Stars invoice through the supported TeleBot wrapper."""
    link = bot.create_invoice_link(
        title="SLH VIP",
        description="SLH VIP: 499 Stars לחודש + חבילת השקה מלאה עד 31.10.",
        payload=f"vip_monthly_{uid}",
        provider_token=None,
        currency=TELEGRAM_STARS_CURRENCY,
        prices=[
            LabeledPrice(label="SLH VIP Monthly", amount=VIP_MONTHLY_STARS)
        ],
        subscription_period=VIP_SUBSCRIPTION_PERIOD,
    )
    if not link:
        raise RuntimeError("TELEGRAM_INVOICE_LINK_EMPTY")
    return str(link)



def _send_vip_invoice(bot, chat_id, uid):
    """Open a recurring Stars subscription using Telegram's invoice-link API."""
    link = _create_vip_invoice_link(bot, uid)
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton(text="⭐ פתיחת מנוי VIP — 499 Stars", url=link))
    bot.send_message(
        chat_id,
        "⭐ מנוי VIP מוכן לתשלום דרך Telegram Stars.",
        reply_markup=markup,
    )
    return "invoice_link"


def _send_pay_menu(bot, chat_id, uid):
    db = state_manager.load_db()
    if uid not in db.get("users", {}):
        bot.send_message(chat_id, "❌ Please /join first.")
        return
    markup = InlineKeyboardMarkup(row_width=1)
    for pack_id, package in STARS_PACKS.items():
        markup.add(InlineKeyboardButton(
            text=package.button_text,
            callback_data=f"pay_{pack_id}"
        ))
    bot.send_message(chat_id, "💎 Credits\n\nבחר חבילה כדי להמשיך דרך Telegram Stars.", reply_markup=markup)



def _commerce_order_counts(db, key):
    root = db.get(key, {}) if isinstance(db, dict) else {}
    rows = list(root.values()) if isinstance(root, dict) else (root if isinstance(root, list) else [])
    statuses = [
        str(row.get("status") or "").strip().upper()
        for row in rows if isinstance(row, dict)
    ]
    fulfilled = sum(status == "FULFILLED" for status in statuses)
    pending = sum(status in {"PAID", "RECOVERABLE", "FULFILLING", "PENDING"} for status in statuses)
    return {"total": len(statuses), "fulfilled": fulfilled, "pending": pending}


def _format_commerce_status(
    *, db, stars_prices, stars_token_configured, card_status, card_items,
    ton_deposits_open, bnb_deposits_open,
):
    """Format a read-only commerce readiness report; never creates orders/invoices."""
    import math

    stars_prices = stars_prices if isinstance(stars_prices, dict) else {}
    card_status = card_status if isinstance(card_status, dict) else {}
    card_items = card_items if isinstance(card_items, list) else []
    products = db.get("products", {}) if isinstance(db, dict) else {}
    products = products if isinstance(products, dict) else {}

    lines = [
        "🛍 SLH COMMERCE — READ ONLY",
        "",
        "⭐ Telegram Stars (digital products)",
    ]
    if not stars_token_configured:
        lines.append("מצב: BLOCKED — BOT_TOKEN אינו מוגדר.")
    elif stars_prices:
        lines.append(f"מצב: קטלוג מוגדר; {len(stars_prices)} מוצר/ים מתומחרים ב-Stars.")
        lines.extend(
            "• " + str(item_id) + ": " + str(price) + "⭐"
            for item_id, price in sorted(stars_prices.items())
        )
        lines.append("רכישה: Mini App → Market או /buystars <item_id>.")
    else:
        lines.append("מצב: אין מוצרי Stars מתומחרים בקטלוג.")

    lines.extend(["", "💳 PayPlus (כרטיסי אשראי — מוצרים פיזיים/חומרה בלבד)"])
    enabled = bool(card_status.get("enabled"))
    configured = bool(card_status.get("configured"))
    sellable, stock_blocked = [], []
    for item in card_items:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id") or "").strip()
        product = products.get(item_id)
        try:
            inventory = int(product.get("inventory", 0) or 0) if isinstance(product, dict) else 0
        except (TypeError, ValueError, OverflowError):
            inventory = 0
        if inventory > 0:
            sellable.append(item)
        else:
            stock_blocked.append(item)

    if not configured:
        lines.append("מצב: BLOCKED — חסרים פרטי ספק/כתובת callback/כתובת ציבורית ב-Railway.")
    elif not enabled:
        lines.append("מצב: CLOSED — CARD_PAYMENTS_OPEN אינו מוגדר במפורש ל-1.")
    elif not card_items:
        lines.append("מצב: BLOCKED — אין מוצרי חומרה עם מחיר ILS מוגדר.")
    elif not sellable:
        lines.append(
            f"מצב: BLOCKED — {len(card_items)} מוצר/ים מתומחרים, אך אין מלאי מוגדר ב-db.products."
        )
    else:
        lines.append(f"מצב: READY לכאורה — {len(sellable)} מוצר/ים מתומחרים ובעלי מלאי.")
        for item in sellable:
            try:
                price = float(item.get("price_ils"))
                price_text = f"{price:.2f} ₪" if math.isfinite(price) and price > 0 else "מחיר לא תקין"
            except (TypeError, ValueError, OverflowError):
                price_text = "מחיר לא תקין"
            lines.append(f"• {item.get('name', item.get('id'))}: {price_text}")
        lines.append("אישור סליקה עדיין דורש עסקת בדיקה מבוקרת ואימות callback אצל PayPlus.")
    if stock_blocked and configured and enabled:
        lines.append(f"מוצרים ללא מלאי תקין: {len(stock_blocked)}.")
    lines.append("הערה: כרגע הסליקה אינה מופעלת אם חסרים ספק, מחירים, מלאי או דגל פתיחה.")

    star_orders = _commerce_order_counts(db, "star_item_orders")
    card_orders = _commerce_order_counts(db, "card_orders")
    lines.extend([
        "",
        "🪙 TON / BNB — תשלום ישיר על מוצר",
        "TON: NOT IMPLEMENTED. מסלול ההפקדה הקיים הוא TON → Credits, לא קניית מוצר.",
        f"שער הפקדות TON בפועל: {'OPEN' if ton_deposits_open else 'CLOSED'}.",
        "BNB: NOT IMPLEMENTED. מסלול ההפקדה הקיים הוא BNB → Credits, לא קניית מוצר.",
        f"שער הפקדות BNB בפועל: {'OPEN' if bnb_deposits_open else 'CLOSED'}.",
        "אין לפתוח את שערי ההפקדה כדי לעקוף checkout של מוצר.",
        "",
        "📦 מצב הזמנות (רשומות מקומיות)",
        f"Stars: {star_orders['total']} הזמנות · {star_orders['fulfilled']} סופקו · {star_orders['pending']} ממתינות/דורשות התאוששות.",
        f"Cards: {card_orders['total']} הזמנות · {card_orders['fulfilled']} סופקו · {card_orders['pending']} ממתינות/דורשות התאוששות.",
    ])

    revenue = db.get("revenue_ledger", []) if isinstance(db, dict) else []
    totals, valid_events = {}, 0
    if isinstance(revenue, list):
        for row in revenue:
            if not isinstance(row, dict) or not str(row.get("reference") or "").strip():
                continue
            try:
                amount = float(row.get("amount"))
            except (TypeError, ValueError, OverflowError):
                continue
            currency = str(row.get("currency") or "").strip().upper()
            if not currency or not math.isfinite(amount) or amount <= 0:
                continue
            totals[currency] = totals.get(currency, 0.0) + amount
            valid_events += 1
    lines.extend(["", f"📈 ספר הכנסות: {valid_events} אירוע/ים מאושרים, לפי המטבע שנרשם."])
    for currency, amount in sorted(totals.items()):
        if currency == "XTR":
            lines.append(f"• XTR (Telegram Stars, לא שקלים): {amount:g}")
        elif currency == "ILS":
            lines.append(f"• ILS (ברוטו שנרשם, לא אישור העברה בנקאית): {amount:.2f} ₪")
        else:
            lines.append(f"• {currency}: {amount:g} (ברוטו שנרשם)")

    lines.extend([
        "",
        "🔒 READ ONLY — הדוח לא יצר חשבונית/הזמנה, לא שינה יתרות ולא פתח שערים.",
        "חשוב: הכנסה שנרשמה אינה בהכרח כסף נטו שכבר שולם לחשבון הבנק.",
    ])
    return "\n".join(lines)


def _commerce_status_report():
    import os
    import state_manager
    from core import card_payment_service
    from core.bnb_gate import bnb_deposits_open as effective_bnb_deposits_open
    from core.ton_deposit_service import deposits_are_open as effective_ton_deposits_open
    from store.stars_purchase_service import get_stars_items

    db = state_manager.load_db()
    stars_prices = get_stars_items()
    card_status = card_payment_service.card_payments_status()
    try:
        card_items = card_payment_service.get_card_items() if card_status.get("configured") else []
    except Exception:
        card_items = []

    try:
        ton_open = bool(effective_ton_deposits_open())
    except Exception:
        ton_open = False
    try:
        bnb_open = bool(effective_bnb_deposits_open())
    except Exception:
        bnb_open = False

    return _format_commerce_status(
        db=db,
        stars_prices=stars_prices,
        stars_token_configured=bool(os.getenv("BOT_TOKEN", "").strip()),
        card_status=card_status,
        card_items=card_items,
        ton_deposits_open=ton_open,
        bnb_deposits_open=bnb_open,
    )


def register_payment_handlers(bot):


    @bot.message_handler(commands=["commerce_status"])
    def commerce_status(message):
        from core.authority import is_owner
        uid = str(getattr(getattr(message, "from_user", None), "id", "") or "")
        chat_type = str(getattr(getattr(message, "chat", None), "type", "") or "").lower()
        if not is_owner(uid):
            bot.reply_to(message, "⛔️ הדוח מיועד לבעלים בלבד.", parse_mode=None)
            return
        if chat_type != "private":
            bot.reply_to(message, "⛔️ דוח המסחר זמין רק בשיחה הפרטית עם הבוט.", parse_mode=None)
            return
        try:
            report = _commerce_status_report()
            bot.reply_to(message, report, parse_mode=None)
        except Exception as exc:
            print("[COMMERCE_STATUS] read-only audit failed:", type(exc).__name__)
            bot.reply_to(
                message,
                "⚠️ לא ניתן לקרוא את מצב המסחר כרגע. לא נוצרו חשבוניות/הזמנות ולא השתנו יתרות או שערים.",
                parse_mode=None,
            )

    @bot.message_handler(commands=['vip'])
    def vip_command(m):
        uid = str(m.from_user.id)
        db = state_manager.load_db()
        user = db.get("users", {}).get(uid, {})
        until = int(user.get("vip_access_until", 0) or 0)
        import time
        if until > int(time.time()):
            bot.send_message(m.chat.id, f"⭐ VIP פעיל עד {time.strftime('%Y-%m-%d', time.gmtime(until))}.")
            return
        try:
            _send_vip_invoice(bot, m.chat.id, uid)
        except Exception as e:
            print(f"[VIP] invoice error: {type(e).__name__}")
            bot.send_message(m.chat.id, "⚠️ לא ניתן לפתוח כרגע את מנוי ה-VIP.")

    @bot.message_handler(commands=['pay'])
    def pay_command(m):
        _send_pay_menu(bot, m.chat.id, str(m.from_user.id))

    @bot.callback_query_handler(func=lambda call: call.data == "slh_credits")
    def credits_callback(call):
        bot.answer_callback_query(call.id)
        _send_pay_menu(bot, call.message.chat.id, str(call.from_user.id))

    @bot.callback_query_handler(func=lambda call: call.data.startswith("pay_"))
    def payment_callback(call):
        pack_id = call.data.split("_", 1)[1]
        if pack_id not in STARS_PACKS:
            bot.answer_callback_query(call.id, "Invalid package.")
            return
        package = STARS_PACKS[pack_id]
        stars, credits, label = package.stars, package.credits, package.label
        try:
            bot.send_invoice(
                chat_id=call.message.chat.id,
                title="SLH Credits",
                description=f"Add {credits} credits to your SLH account",
                invoice_payload=f"credits_{credits}_{call.from_user.id}",
                provider_token=PROVIDER_TOKEN,
                currency=TELEGRAM_STARS_CURRENCY,
                prices=[LabeledPrice(label=label, amount=stars)],
                start_parameter=f"credits_{credits}",
                need_name=False,
                need_phone_number=False,
                need_email=False,
                is_flexible=False
            )
            bot.answer_callback_query(call.id)
            print(f"[PAY] Invoice sent to {call.from_user.id} for {stars} Stars")
        except Exception as e:
            print(f"[PAY] Error sending invoice: {e}")
            bot.answer_callback_query(call.id, "Failed to send invoice. Try again later.")

    @bot.pre_checkout_query_handler(func=lambda query: True)
    def pre_checkout(query: PreCheckoutQuery):
        raw = str(query.invoice_payload or "")
        if raw.startswith("item_") and raw.endswith("_" + str(query.from_user.id)):
            item_id = raw[5:-(len(str(query.from_user.id)) + 1)]
            expected_stars = get_stars_price(item_id)
            try:
                valid_amount = int(query.total_amount) == expected_stars
            except (TypeError, ValueError):
                valid_amount = False
            if query.currency == TELEGRAM_STARS_CURRENCY and valid_amount:
                bot.answer_pre_checkout_query(query.id, ok=True)
            else:
                bot.answer_pre_checkout_query(query.id, ok=False, error_message="Invalid item price.")
            return

        if raw == f"vip_monthly_{query.from_user.id}":
            try:
                valid_amount = int(query.total_amount) == VIP_MONTHLY_STARS
            except (TypeError, ValueError):
                valid_amount = False
            if query.currency == "XTR" and valid_amount:
                bot.answer_pre_checkout_query(query.id, ok=True)
            else:
                bot.answer_pre_checkout_query(
                    query.id,
                    ok=False,
                    error_message="Invalid VIP price.",
                )
            return

        parts = raw.split("_")
        if len(parts) != 3 or parts[0] != "credits" or parts[2] != str(query.from_user.id):
            bot.answer_pre_checkout_query(query.id, ok=False, error_message="Invalid payment recipient.")
            return
        try:
            expected_credits = int(parts[1])
        except Exception:
            bot.answer_pre_checkout_query(query.id, ok=False, error_message="Invalid payment package.")
            return
        package = _resolve_stars_package(expected_credits, query.total_amount)
        if query.currency != TELEGRAM_STARS_CURRENCY or package is None:
            bot.answer_pre_checkout_query(query.id, ok=False, error_message="Invalid payment package or price.")
            return
        bot.answer_pre_checkout_query(query.id, ok=True)

    @bot.message_handler(content_types=['successful_payment'])
    def successful_payment(m):
        uid = str(m.from_user.id)
        payment = m.successful_payment
        payload = str(payment.invoice_payload or "")

        if payload == f"vip_monthly_{uid}":
            import time
            charge_id = str(payment.telegram_payment_charge_id or "").strip()
            if payment.currency != TELEGRAM_STARS_CURRENCY or int(payment.total_amount) != VIP_MONTHLY_STARS or not charge_id:
                bot.send_message(m.chat.id, "❌ תשלום VIP לא תקין.")
                return

            try:
                result = stars_payment_authority.record_vip_subscription_payment(
                    uid=uid,
                    stars_paid=payment.total_amount,
                    charge_id=charge_id,
                    recurring=bool(getattr(payment, "is_recurring", False)),
                    first_recurring=bool(getattr(payment, "is_first_recurring", False)),
                )
            except ValueError as exc:
                print(f"[VIP] authority rejected payment: {type(exc).__name__}")
                bot.send_message(m.chat.id, "❌ תשלום VIP לא תקין.")
                return

            if result.get("status") == "conflict":
                print("[VIP] Stars charge/revenue conflict; benefits blocked for review")
                bot.send_message(
                    m.chat.id,
                    "⚠️ נמצאה אי־התאמה בפרטי תשלום VIP שכבר נרשם. לא בוצעה הפעלה נוספת. "
                    "אל תשלם שוב; פנה ל-/paysupport לבדיקה.",
                )
                return

            if result["status"] == "duplicate":
                message = (
                    "ℹ️ תשלום VIP כבר עובד. החבילה נשמרת כל עוד המנוי פעיל."
                )
            elif result.get("launch_offer_qualified") and result.get("fulfillment_status") == "completed":
                message = (
                    "✅ VIP הופעל לחודש.\n"
                    "🎁 חבילת ההשקה הופעלה: 300 Credits + Agent OS + אימוג'י VIP זהוב + עד 4 סוכנים.\n"
                    "החיוב יתחדש אוטומטית לפי מנוי Telegram Stars."
                )
            else:
                message = (
                    "✅ VIP הופעל לחודש.\n"
                    "⚠️ תשלום VIP נקלט, אך השלמת חבילת ההשקה ממתינה לריצוי אוטומטי.\n"
                    "החיוב יתחדש אוטומטית לפי מנוי Telegram Stars."
                )
            bot.send_message(m.chat.id, message)
            return
            return

        if payload.startswith("item_") and payload.endswith("_" + uid):
            item_id = payload[5:-(len(uid)+1)]
            charge_id = str(payment.telegram_payment_charge_id or "").strip()
            expected_stars = get_stars_price(item_id)
            try:
                valid_amount = int(payment.total_amount) == expected_stars
            except (TypeError, ValueError):
                valid_amount = False
            if payment.currency != TELEGRAM_STARS_CURRENCY or not charge_id or not valid_amount:
                bot.send_message(m.chat.id, "❌ Invalid Stars item payment.")
                return
            try:
                result = purchase_item_with_stars(
                    uid=uid,
                    item_id=item_id,
                    stars_paid=payment.total_amount,
                    charge_id=charge_id,
                )
            except Exception as e:
                print(f"[PAY] STAR item fulfillment failed: {type(e).__name__}")
                bot.send_message(m.chat.id, "⚠️ Payment was received but fulfillment failed safely. Please contact /paysupport.")
                return
            if result["status"] == "CONFLICT":
                print("[PAY] Telegram Stars item charge conflict; fulfillment blocked")
                bot.send_message(
                    m.chat.id,
                    "⚠️ התשלום התקבל אך פרטי החיוב אינם תואמים לרשומה קיימת. לא בוצעה אספקה. "
                    "אל תנסה לשלם שוב; פנה ל-/paysupport לבדיקה.",
                )
                return
            if result["status"] == "DUPLICATE":
                bot.send_message(m.chat.id, "ℹ️ This item payment was already processed.")
                return
            if result["status"] == "RECOVERABLE":
                bot.send_message(m.chat.id, "⚠️ Payment received. Fulfillment needs recovery; retry is safe and will not charge again.")
                return
            bot.send_message(m.chat.id, "✅ Payment received and item fulfilled.\n"
                              f"Item: {item_id}\nStars: {payment.total_amount}\n"
                              f"Ref: {payment.telegram_payment_charge_id[:12]}")
            return

        parts = payload.split("_")
        if len(parts) != 3 or parts[0] != "credits" or parts[2] != uid:
            bot.send_message(m.chat.id, "❌ Invalid payment payload.")
            return
        try:
            credits = int(parts[1])
        except Exception:
            bot.send_message(m.chat.id, "❌ Error parsing credits.")
            return
        package = _resolve_stars_package(credits, payment.total_amount)
        if payment.currency != TELEGRAM_STARS_CURRENCY or package is None:
            bot.send_message(m.chat.id, "❌ Invalid payment package or price.")
            return
        try:
            db = state_manager.load_db()
            referrer_uid = db.get("users", {}).get(uid, {}).get("referral", {}).get("referred_by")
            result = stars_payment_authority.record_stars_payment(
                uid=uid,
                credits=package[2],
                stars_paid=package[1],
                currency=payment.currency,
                telegram_payment_charge_id=payment.telegram_payment_charge_id,
                provider_payment_charge_id=payment.provider_payment_charge_id,
                referrer_uid=referrer_uid,
                meta={"source": "telegram_successful_payment", "invoice_payload": payload, "package_id": package[0]},
            )
            result_status = str(result.get("status") or "").lower()
            if result_status == "conflict":
                print("[PAY] Telegram Stars charge replay conflict; manual review required")
                bot.send_message(
                    m.chat.id,
                    "⚠️ נמצאה אי־התאמה בפרטי תשלום שכבר נרשם. לא בוצע זיכוי נוסף בבקשה זו. "
                    "אל תנסה לשלם שוב; פנה ל-/paysupport לבדיקה.",
                )
                return
            if result_status == "duplicate":
                bot.send_message(m.chat.id, "ℹ️ This payment was already processed.")
                return
            if result.get("revenue_status") == "conflict":
                print("[PAY] Stars revenue ledger conflict after primary payment commit; manual review required")
                bot.send_message(
                    m.chat.id,
                    "⚠️ התשלום נרשם, אך קיימת אי־התאמה בספר ההכנסות. אל תשלם שוב. "
                    "פנה ל-/paysupport כדי שנבדוק את הרישום לפני כל פעולה נוספת.",
                )
                return
            bot.send_message(m.chat.id, f"✅ Payment received! {package[2]} credits added.\nYour balance: {result['credits']} credits.")
        except Exception as e:
            print(f"[PAY] Atomic payment failed: {type(e).__name__}")
            bot.send_message(m.chat.id, "⚠️ Payment processing failed safely. Please contact /paysupport.")


    @bot.message_handler(commands=['cardpay'])
    def cardpay_command(m):
        """Hosted card checkout for configured physical/hardware products only."""
        from core import card_payment_service

        parts = (m.text or "").split(maxsplit=1)
        if len(parts) == 1:
            try:
                items = card_payment_service.get_card_items()
            except Exception:
                items = []
            if not items:
                bot.send_message(
                    m.chat.id,
                    "💳 סליקת כרטיסים אינה זמינה כרגע.\n"
                    "המסלול מופעל רק למוצרים פיזיים שהוגדרו מראש לסליקה.",
                )
                return
            markup = InlineKeyboardMarkup(row_width=1)
            for item in items:
                markup.add(
                    InlineKeyboardButton(
                        text=f"💳 {item['name']} — {item['price_ils']:.2f} ₪",
                        callback_data=f"cardpay_{item['id']}",
                    )
                )
            bot.send_message(
                m.chat.id,
                "💳 רכישה בכרטיס\n\n"
                "האפשרות הזו מיועדת למוצרי חומרה/מוצרים פיזיים בלבד.",
                reply_markup=markup,
            )
            return

        item_id = parts[1].strip()
        try:
            result = card_payment_service.create_card_checkout(
                uid=str(m.from_user.id),
                item_id=item_id,
            )
            markup = InlineKeyboardMarkup(row_width=1)
            markup.add(
                InlineKeyboardButton(
                    text="💳 המשך לתשלום מאובטח",
                    url=result["payment_page_link"],
                )
            )
            bot.send_message(
                m.chat.id,
                "✅ הזמנת כרטיס נפתחה.\n"
                f"מוצר: {result['item_name']}\n"
                f"סכום: {result['amount']:.2f} ₪\n"
                "הזמנה תסופק רק לאחר אישור שרת של ספק התשלום.",
                reply_markup=markup,
            )
        except ValueError as exc:
            code = str(exc)
            messages = {
                "CARD_ONLY_PHYSICAL_PRODUCTS": "⛔ כרטיסים זמינים רק למוצרים פיזיים/חומרה. מוצרים דיגיטליים ו-Credits נרכשים ב-Telegram Stars.",
                "CARD_ITEM_PRICE_NOT_CONFIGURED": "⏳ המחיר של המוצר הזה לסליקת כרטיסים עדיין לא הוגדר.",
                "INVALID_USER_ID": "❌ מזהה משתמש לא תקין.",
                "ITEM_NOT_FOUND": "❌ המוצר לא נמצא.",
            }
            bot.send_message(m.chat.id, messages.get(code, "⚠️ לא ניתן לפתוח כרגע תשלום בכרטיס."))
        except RuntimeError as exc:
            code = str(exc)
            if code == "CARD_PAYMENTS_CLOSED":
                msg = "⛔ סליקת כרטיסים סגורה כרגע."
            elif code == "CARD_PROVIDER_NOT_CONFIGURED":
                msg = "⏳ ספק הסליקה עדיין לא הוגדר בשרת."
            else:
                msg = "⚠️ סליקת כרטיסים אינה זמינה כרגע."
            bot.send_message(m.chat.id, msg)
        except Exception as exc:
            print(f"[CARD] checkout error: {type(exc).__name__}")
            bot.send_message(m.chat.id, "⚠️ לא ניתן לפתוח כרגע תשלום בכרטיס.")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("cardpay_"))
    def cardpay_callback(call):
        from core import card_payment_service

        item_id = call.data[len("cardpay_"):].strip()
        if not item_id:
            bot.answer_callback_query(call.id, "מוצר לא תקין.")
            return
        try:
            result = card_payment_service.create_card_checkout(
                uid=str(call.from_user.id),
                item_id=item_id,
            )
            markup = InlineKeyboardMarkup(row_width=1)
            markup.add(
                InlineKeyboardButton(
                    text="💳 המשך לתשלום מאובטח",
                    url=result["payment_page_link"],
                )
            )
            bot.answer_callback_query(call.id)
            bot.send_message(
                call.message.chat.id,
                "💳 תשלום בכרטיס מוכן.\n"
                f"{result['item_name']} — {result['amount']:.2f} ₪",
                reply_markup=markup,
            )
        except Exception as exc:
            print(f"[CARD] callback error: {type(exc).__name__}")
            bot.answer_callback_query(call.id, "לא ניתן לפתוח תשלום כרגע.", show_alert=True)

    @bot.message_handler(commands=['card_orders'])
    def card_orders(m):
        from core import card_payment_service

        try:
            recovery = card_payment_service.reconcile_card_orders(
                uid=str(m.from_user.id),
                limit=10,
            )
            db = state_manager.load_db()
            orders = db.get("card_orders", {})
            mine = [
                row for row in orders.values()
                if isinstance(row, dict) and str(row.get("uid")) == str(m.from_user.id)
            ] if isinstance(orders, dict) else []
            recent = mine[-10:]
            if not recent:
                bot.send_message(m.chat.id, "📦 אין הזמנות כרטיס רשומות כרגע.")
                return

            lines = [
                "💳 הזמנות כרטיס אחרונות:",
                f"🔄 ניסיונות אספקה שבוצעו: {recovery.get('attempted', 0)}",
            ]
            for row in recent:
                lines.append(
                    f"• {row.get('item_name', row.get('item_id', 'item'))} — "
                    f"{row.get('amount', 0):.2f} ₪ — {row.get('status', '?')}"
                )
            bot.send_message(m.chat.id, "\n".join(lines))
        except Exception as exc:
            print(f"[CARD] order status error: {type(exc).__name__}")
            bot.send_message(m.chat.id, "⚠️ לא ניתן לטעון כרגע את הזמנות הכרטיס.")

    @bot.message_handler(commands=['my_orders'])
    def my_orders(m):
        uid = str(m.from_user.id)
        try:
            import state_manager
            from store.fulfillment_recovery import (
                recover_paid_orders,
                reconcile_telegram_stars,
            )

            reconcile_telegram_stars(uid=uid)
            db = state_manager.load_db()
            orders = db.get("star_item_orders", {})
            mine = [
                row for row in orders.values()
                if isinstance(row, dict) and str(row.get("uid")) == uid
            ] if isinstance(orders, dict) else []

            pending = [
                row for row in mine
                if row.get("status") in {"RECOVERABLE", "PAID"}
            ]

            if pending:
                # Retry fulfillment only; no new payment is created.
                recovery = recover_paid_orders(limit=min(len(pending), 10), uid=uid)
                remaining = len([
                    row for row in (state_manager.load_db().get("star_item_orders", {}) or {}).values()
                    if isinstance(row, dict)
                    and str(row.get("uid")) == uid
                    and row.get("status") in {"RECOVERABLE", "PAID"}
                ])
                bot.send_message(
                    m.chat.id,
                    "🔄 בדקתי הזמנות ששולמו אך לא הושלמו.\n"
                    f"✅ ניסיונות מוצלחים: {recovery.get('success', 0)}\n"
                    f"⚠️ עדיין דורשות טיפול: {remaining}"
                )
                return

            recent = mine[-10:]
            if not recent:
                bot.send_message(m.chat.id, "📦 אין הזמנות Stars רשומות כרגע.")
                return

            lines = ["📦 ההזמנות האחרונות שלך:"]
            for row in recent:
                lines.append(
                    f"• {row.get('item_name', row.get('item_id', 'item'))} — "
                    f"{row.get('stars_paid', 0)}⭐ — {row.get('status', '?')}"
                )
            bot.send_message(m.chat.id, "\n".join(lines))
        except Exception as exc:
            print(f"[ORDERS] recovery/status error: {type(exc).__name__}")
            bot.send_message(m.chat.id, "⚠️ לא ניתן לטעון כרגע את סטטוס ההזמנות.")

    @bot.message_handler(commands=['paysupport'])
    def paysupport(m):
        bot.send_message(m.chat.id, "💳 SLH Payment Support\nFor a payment issue, send the payment date/time, Stars amount, and payment reference if available.")

    @bot.message_handler(commands=['history'])
    def history(m):
        uid = str(m.from_user.id)
        db = state_manager.load_db()
        rows = [
            row for row in db.get("ledger", [])
            if str(row.get("uid")) == uid
        ]
        if not rows:
            bot.send_message(m.chat.id, "📜 אין עדיין תנועות Credits.")
            return

        def _history_reason(row):
            reason = str(row.get("reason", "")).strip()
            labels = {
                "arcade:entry": "Arcade",
                "staking:stake": "Staking",
                "staking:unstake": "Unstaking",
                "staking:reward_claim": "Staking reward",
                "task:completion_reward": "Task reward",
                "bridge:spend": "Spend",
                "bridge:add_credits": "Credits added",
            }
            return labels.get(reason, reason or "Credit movement")

        lines = ["📜 היסטוריית Credits:"]
        for row in rows[-10:]:
            amount = row.get("amount", 0)
            sign = "+" if isinstance(amount, (int, float)) and amount > 0 else ""
            amount_text = f"{sign}{amount:g}" if isinstance(amount, (int, float)) else str(amount)
            date_text = str(row.get("time", ""))[:10]
            lines.append(
                f"▫️ {amount_text} Credits — {_history_reason(row)} — {date_text}"
            )

        bot.send_message(m.chat.id, "\n".join(lines))

    @bot.message_handler(commands=['fakepay_disabled'])
    def fakepay(m):
        from admin_utils import is_admin
        if not is_admin(m):
            return
        if os.getenv("SLH_ALPHA_TEST_MODE", "0") != "1":
            bot.send_message(m.chat.id, "⛔ Fake payments are disabled in Alpha.")
            return
        uid = str(m.from_user.id)
        try:
            from core import economy_service
            balance = economy_service.record_transaction(
                uid=uid, amount=100, reason="admin:test_payment",
                meta={"source": "fakepay", "test_mode": True}
            )
            bot.send_message(m.chat.id, f"💰 100 test credits added. Balance: {balance}")
        except Exception as e:
            bot.send_message(m.chat.id, "❌ Test payment failed safely.")
            print(f"[PAY] fakepay error: {type(e).__name__}")


def register(bot):
    register_payment_handlers(bot)