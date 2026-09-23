"""Unified Gifts / Rewards center.

User-facing entry point for Credits gifts and existing SLH airdrop eligibility.
Credits gifts are funded by the sender's existing Credits balance through the
canonical idempotent transfer authority. SLH airdrops use the canonical
distribution authority and never mint supply.
"""

from telebot import types

import state_manager
from core import economy_service


def _wallet(uid):
    db = state_manager.load_db()
    return (db.get("users", {}).get(str(uid), {}) or {}).get("wallet", {}) or {}


def _points(uid):
    db = state_manager.load_db()
    user = db.get("users", {}).get(str(uid), {}) or {}
    return int(((user.get("gamification") or {}).get("points", 0) or 0))


def _gift_history(uid, limit=8):
    db = state_manager.load_db()
    rows = []
    for entry in reversed(db.get("ledger", []) or []):
        if str(entry.get("uid")) != str(uid):
            continue
        reason = str(entry.get("reason", ""))
        if reason not in {"p2p:transfer_sent", "p2p:transfer_received"}:
            continue
        meta = entry.get("meta") or {}
        rows.append({
            "time": entry.get("time"),
            "direction": "sent" if reason.endswith("sent") else "received",
            "amount": abs(float(entry.get("amount", 0) or 0)),
            "peer": (
                meta.get("recipient_uid")
                if reason.endswith("sent")
                else meta.get("sender_uid")
            ),
            "transfer_id": meta.get("transfer_id"),
        })
        if len(rows) >= limit:
            break
    return rows


def _status_text(uid):
    wallet = _wallet(uid)
    credits = wallet.get("credits", 0)
    points = _points(uid)

    try:
        from core.holiday_campaign import eligibility
        decision = eligibility(str(uid))
    except Exception as exc:
        print(f"[GIFTS] campaign status failed: {type(exc).__name__}")
        decision = {"eligible": False, "reason": "STATUS_UNAVAILABLE"}

    if decision.get("eligible"):
        air_line = f"🪂 Airdrop: ✅ זכאי ל-{decision.get('amount', 0):,} SLH"
    else:
        reasons = {
            "USER_NOT_FOUND": "המשתמש עדיין לא רשום",
            "NO_CAMPAIGN_ENTRY": "אין כניסה לקמפיין",
            "NOT_JOINED": "יש להשלים /join",
            "NO_SUCCESSFUL_REFERRAL": "נדרש לפחות Referral מוצלח אחד",
            "STATUS_UNAVAILABLE": "לא ניתן לבדוק כרגע",
        }
        air_line = f"🪂 Airdrop: {reasons.get(decision.get('reason'), 'לא זכאי כרגע')}"

    return (
        "🎁 מרכז מתנות ותגמולים\n\n"
        f"💰 Credits: {credits}\n"
        f"⭐ Points: {points:,}\n"
        f"{air_line}\n\n"
        "כאן מרוכזים מתנות, העברות ו-Airdrop במקום אחד."
    )


def _home_markup(uid):
    markup = types.InlineKeyboardMarkup(row_width=2)
    db = state_manager.load_db()
    if str(uid) not in (db.get("users", {}) or {}):
        markup.add(types.InlineKeyboardButton("🚀 הצטרף ל-SLH", callback_data="start_join"))
        markup.add(types.InlineKeyboardButton("📖 עזרה", callback_data="show_help"))
        return markup
    markup.add(
        types.InlineKeyboardButton("🎁 שלח מתנה", callback_data="gifts:send"),
        types.InlineKeyboardButton("🪂 בדוק Airdrop", callback_data="gifts:airdrop"),
    )
    markup.add(
        types.InlineKeyboardButton("📜 היסטוריית מתנות", callback_data="gifts:history"),
        types.InlineKeyboardButton("🏆 Rewards", callback_data="gifts:rewards"),
    )
    markup.add(
        types.InlineKeyboardButton("👛 ארנק", callback_data="gifts:wallet"),
        types.InlineKeyboardButton("👥 הזמנה", callback_data="gifts:share"),
    )

    try:
        from core.authority import has_permission
        if has_permission(str(uid), "alpha.distribute"):
            markup.add(
                types.InlineKeyboardButton(
                    "👑 חלוקת SLH / AIR",
                    callback_data="gifts:admin_air",
                )
            )
    except Exception:
        pass

    return markup


def _send_home(bot, chat_id, uid, *, edit_message=None):
    text = _status_text(uid)
    markup = _home_markup(uid)

    if edit_message is not None:
        try:
            bot.edit_message_text(
                text,
                chat_id=edit_message.chat.id,
                message_id=edit_message.message_id,
                reply_markup=markup,
            )
            return
        except Exception:
            pass

    bot.send_message(chat_id, text, reply_markup=markup)


def register(bot):
    @bot.message_handler(commands=["gifts", "gift_center"])
    def gifts(message):
        uid = str(message.from_user.id)
        _send_home(bot, message.chat.id, uid)

    @bot.message_handler(commands=["gift"])
    def gift(message):
        uid = str(message.from_user.id)
        parts = (message.text or "").split()

        if len(parts) != 3:
            bot.reply_to(
                message,
                "🎁 שימוש:\n"
                "/gift <recipient_uid> <amount>\n\n"
                "המתנה יוצאת מיתרת ה-Credits שלך."
            )
            return

        recipient_uid = str(parts[1]).strip()
        try:
            amount = float(parts[2])
        except (TypeError, ValueError):
            bot.reply_to(message, "❌ סכום מתנה לא תקין.")
            return

        idempotency_key = f"TG-GIFT-{uid}-{message.message_id}"
        try:
            result = economy_service.transfer_credits(
                sender_uid=uid,
                recipient_uid=recipient_uid,
                amount=amount,
                idempotency_key=idempotency_key,
                meta={
                    "source": "telegram_gift",
                    "message_id": message.message_id,
                },
            )
        except ValueError as exc:
            messages = {
                "SELF_TRANSFER": "❌ אי אפשר לשלוח מתנה לעצמך.",
                "SENDER_NOT_FOUND": "❌ חשבון השולח לא נמצא.",
                "RECIPIENT_NOT_FOUND": "❌ חשבון המקבל לא נמצא.",
                "INVALID_TRANSFER_AMOUNT": "❌ סכום המתנה חייב להיות גדול מאפס.",
                "INSUFFICIENT_CREDITS": "❌ אין לך מספיק Credits למתנה הזו.",
                "INVALID_IDEMPOTENCY_KEY": "❌ לא ניתן ליצור מזהה מתנה תקין.",
            }
            bot.reply_to(message, messages.get(str(exc), "❌ שליחת המתנה נכשלה."))
            return
        except Exception:
            bot.reply_to(message, "❌ שגיאה פנימית. המתנה לא בוצעה.")
            return

        if result.get("status") == "duplicate":
            bot.reply_to(
                message,
                "ℹ️ המתנה הזו כבר בוצעה.\n"
                f"🧾 Transfer ID: {result.get('transfer_id')}",
            )
            return

        bot.reply_to(
            message,
            "🎁 המתנה נשלחה בהצלחה!\n\n"
            f"💰 {result.get('amount')} Credits\n"
            f"👤 למשתמש: {result.get('recipient_uid')}\n"
            f"💳 היתרה שלך: {result.get('sender_balance')} Credits\n"
            f"🧾 Transfer ID: {result.get('transfer_id')}",
        )

        try:
            bot.send_message(
                int(recipient_uid),
                "🎁 קיבלת מתנה ב-SLH OS!\n\n"
                f"💰 סכום: {result.get('amount')} Credits\n"
                "פתח /gifts כדי לראות את מרכז המתנות שלך.",
                reply_markup=_home_markup(recipient_uid),
            )
        except Exception as exc:
            print(f"[GIFTS] recipient notification failed: {type(exc).__name__}")

    @bot.callback_query_handler(func=lambda call: call.data == "gifts:send")
    def gift_send(call):
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "🎁 שליחת מתנה\n\n"
            "הזן את ה-UID והסכום:\n"
            "/gift <recipient_uid> <amount>\n\n"
            "הסכום יורד מיתרת ה-Credits שלך ונרשם בהיסטוריה.",
        )

    @bot.callback_query_handler(func=lambda call: call.data == "gifts:airdrop")
    def gift_airdrop(call):
        uid = str(call.from_user.id)
        bot.answer_callback_query(call.id)
        try:
            from core.holiday_campaign import eligibility
            decision = eligibility(uid)
        except Exception as exc:
            bot.send_message(
                call.message.chat.id,
                f"❌ לא ניתן לבדוק Airdrop כרגע: {type(exc).__name__}",
            )
            return

        if not decision.get("eligible"):
            reasons = {
                "USER_NOT_FOUND": "החשבון עדיין לא רשום.",
                "NO_CAMPAIGN_ENTRY": "אין רישום לכניסת הקמפיין.",
                "NOT_JOINED": "יש להשלים /join לפני המימוש.",
                "NO_SUCCESSFUL_REFERRAL": "נדרש לפחות Referral מוצלח אחד.",
            }
            bot.send_message(
                call.message.chat.id,
                "🪂 סטטוס Airdrop\n\n"
                f"❌ {reasons.get(decision.get('reason'), 'לא זכאי כרגע.')}",
                reply_markup=_home_markup(uid),
            )
            return

        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton(
                f"✅ מימוש {decision.get('amount', 0):,} SLH",
                callback_data="gifts:claim_air",
            )
        )
        markup.add(types.InlineKeyboardButton("⬅️ חזרה", callback_data="gifts:home"))
        bot.send_message(
            call.message.chat.id,
            "🪂 Airdrop זמין לך.\n\n"
            f"🎁 סכום: {decision.get('amount', 0):,} SLH\n"
            f"👥 Referrals מוצלחים: {decision.get('successful_referrals', 0)}\n\n"
            "המימוש נעשה דרך סמכות חלוקת ה-SLH של המערכת; אין כאן mint.",
            reply_markup=markup,
        )

    @bot.callback_query_handler(func=lambda call: call.data == "gifts:claim_air")
    def gift_claim_air(call):
        uid = str(call.from_user.id)
        bot.answer_callback_query(call.id, "🪂 בודק זכאות...")
        try:
            from core.holiday_campaign import settle
            result = settle(uid)
        except PermissionError:
            bot.send_message(
                call.message.chat.id,
                "⛔️ חלוקת ה-Airdrop אינה מורשית כרגע.",
                reply_markup=_home_markup(uid),
            )
            return
        except ValueError as exc:
            bot.send_message(
                call.message.chat.id,
                f"❌ מימוש ה-Airdrop נדחה: {exc}",
                reply_markup=_home_markup(uid),
            )
            return
        except Exception as exc:
            print(f"[GIFTS] air settle failed: {type(exc).__name__}")
            bot.send_message(
                call.message.chat.id,
                "❌ מימוש ה-Airdrop נכשל. לא בוצע חיוב חלקי.",
                reply_markup=_home_markup(uid),
            )
            return

        settlement = result.get("settlement") or {}
        status = settlement.get("status")
        if status == "already_completed":
            bot.send_message(
                call.message.chat.id,
                "ℹ️ ה-Airdrop כבר מומש בעבר.\n"
                f"🪙 {settlement.get('amount', result.get('amount', 0)):g} SLH\n"
                f"🆔 {settlement.get('event_id', '')}",
                reply_markup=_home_markup(uid),
            )
            return

        bot.send_message(
            call.message.chat.id,
            "✅ ה-Airdrop מומש בהצלחה!\n\n"
            f"🪙 {settlement.get('amount', result.get('amount', 0)):g} SLH\n"
            f"🆔 {settlement.get('event_id', '')}",
            reply_markup=_home_markup(uid),
        )

    @bot.callback_query_handler(func=lambda call: call.data == "gifts:history")
    def gift_history(call):
        uid = str(call.from_user.id)
        bot.answer_callback_query(call.id)
        rows = _gift_history(uid)
        if not rows:
            text = "📜 היסטוריית מתנות\n\nאין עדיין העברות Credits שמסווגות כמתנה."
        else:
            lines = ["📜 היסטוריית מתנות", ""]
            for row in rows:
                arrow = "📤" if row["direction"] == "sent" else "📥"
                peer_label = row["peer"] or "—"
                lines.append(f"{arrow} {row['amount']:g} Credits · {peer_label}")
            text = "\n".join(lines)

        bot.send_message(
            call.message.chat.id,
            text,
            reply_markup=_home_markup(uid),
        )

    @bot.callback_query_handler(func=lambda call: call.data == "gifts:rewards")
    def gift_rewards(call):
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "🏆 Rewards\n\n"
            "שלח /rewards כדי לראות Points, Referrals וזכאות לקמפיין.",
            reply_markup=_home_markup(str(call.from_user.id)),
        )

    @bot.callback_query_handler(func=lambda call: call.data == "gifts:wallet")
    def gift_wallet(call):
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "👛 הארנק שלך נמצא כאן:\n/wallet",
            reply_markup=_home_markup(str(call.from_user.id)),
        )

    @bot.callback_query_handler(func=lambda call: call.data == "gifts:share")
    def gift_share(call):
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "👥 הזמנה ו-Referral:\n/share",
            reply_markup=_home_markup(str(call.from_user.id)),
        )

    @bot.callback_query_handler(func=lambda call: call.data == "gifts:admin_air")
    def gift_admin_air(call):
        uid = str(call.from_user.id)
        try:
            from core.authority import has_permission
            allowed = has_permission(uid, "alpha.distribute")
        except Exception:
            allowed = False
        bot.answer_callback_query(call.id)
        if not allowed:
            bot.send_message(call.message.chat.id, "⛔️ אין לך הרשאת חלוקת SLH.")
            return
        bot.send_message(
            call.message.chat.id,
            "👑 חלוקת SLH / AIR\n\n"
            "/airdrop_slh <uid> <amount> <event_id>\n\n"
            "event_id חובה כדי למנוע חלוקה כפולה.\n"
            "המסלול משתמש ב-SLH קיים ואינו מייצר supply חדש.",
            reply_markup=_home_markup(uid),
        )

    @bot.callback_query_handler(func=lambda call: call.data == "gifts:home")
    def gift_home(call):
        uid = str(call.from_user.id)
        bot.answer_callback_query(call.id)
        _send_home(bot, call.message.chat.id, uid, edit_message=call.message)

    print("✅ gifts handler loaded")
