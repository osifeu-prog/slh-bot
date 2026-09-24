"""TON deposit commands backed by verified wallet binding.

/ton_address exposes the configured treasury and the user's personal memo after
the user is instructed to bind a TON wallet. /ton_check verifies one TX and
/ton_paid scans recent inbound transfers. All credits flow through the single
core.ton_deposit_service authority.
"""

def register(bot, context=None):
    from core.ton_deposit_service import (
        credit_new_ton_deposits,
        memo_for,
        settle_ton_deposit,
    )
    from core.ton_wallet_binding import get_ton_binding
    import os
    import state_manager

    def is_open():
        return os.getenv("TON_DEPOSITS_OPEN", "0").strip() == "1"

    def settings():
        s = state_manager.load_db().get("ton_settings", {}) or {}
        rate = s.get("credits_per_ton")
        if rate in (None, "", 0):
            rate = s.get("rate")
        return s.get("wallet"), rate

    @bot.message_handler(commands=["ton_address", "ton_deposit"])
    def ton_address_cmd(msg):
        if not is_open():
            bot.reply_to(msg, "⛔ הפקדות TON סגורות כרגע. אל תשלח TON עד להודעה.")
            return

        wallet, rate = settings()
        if not wallet or not rate:
            bot.reply_to(msg, "⛔ הפקדות TON לא מוגדרות.")
            return

        uid = msg.from_user.id
        binding = get_ton_binding(uid)
        binding_line = (
            f"✅ ארנק מאומת: <code>{binding.get('address')}</code>"
            if binding
            else "⚠️ לפני שליחת TON יש לאמת את הארנק שלך דרך Mini App."
        )
        bot.reply_to(
            msg,
            "💎 <b>הפקדת TON</b>\n\n"
            f"{binding_line}\n\n"
            f"כתובת האוצר:\n<code>{wallet}</code>\n\n"
            f"קוד Comment/Memo אישי:\n<code>{memo_for(uid)}</code>\n\n"
            f"שער: <b>1 TON = {rate:g} Credits</b>\n\n"
            "הזיכוי דורש גם ארנק TON מאומת וגם את ההערה המדויקת. "
            "שליחה מארנק אחר לא תזוכה לחשבון.\n"
            "לאחר השליחה: /ton_paid או /ton_check &lt;TX hash&gt;.",
            parse_mode="HTML",
        )

    @bot.message_handler(commands=["ton_check"])
    def ton_check_cmd(msg):
        if not is_open():
            bot.reply_to(msg, "⛔ הפקדות TON סגורות כרגע.")
            return
        parts = (msg.text or "").split()
        if len(parts) != 2:
            bot.reply_to(msg, "שימוש: /ton_check &lt;TX hash&gt;", parse_mode="HTML")
            return
        try:
            result = settle_ton_deposit(msg.from_user.id, parts[1])
            if result["idempotent"]:
                bot.reply_to(
                    msg,
                    f"♻️ העסקה כבר זוכתה בעבר.\nTX: <code>{result['tx_hash']}</code>",
                    parse_mode="HTML",
                )
            else:
                bot.reply_to(
                    msg,
                    "✅ הפקדת TON אומתה וזוכתה.\n"
                    f"{result['amount_ton']:g} TON → {result['credits']:g} Credits\n"
                    f"TX: <code>{result['tx_hash']}</code>",
                    parse_mode="HTML",
                )
        except ValueError as exc:
            bot.reply_to(msg, f"⚠️ {str(exc)}")
        except Exception as exc:  # noqa: BLE001
            print("[TON] /ton_check error:", type(exc).__name__, str(exc)[:200])
            bot.reply_to(msg, "⚠️ לא הצלחתי לבדוק את העסקה כרגע. נסה שוב בעוד דקה.")

    @bot.message_handler(commands=["ton_paid"])
    def ton_paid_cmd(msg):
        if not is_open():
            bot.reply_to(msg, "⛔ הפקדות TON סגורות כרגע.")
            return
        try:
            credited = credit_new_ton_deposits(msg.from_user.id)
        except ValueError as exc:
            bot.reply_to(msg, f"⚠️ {str(exc)}")
            return
        except Exception as exc:  # noqa: BLE001
            print("[TON] /ton_paid error:", type(exc).__name__, str(exc)[:200])
            bot.reply_to(msg, "⚠️ לא הצלחתי לבדוק כרגע. נסה שוב בעוד דקה.")
            return

        if not credited:
            bot.reply_to(
                msg,
                "⏳ לא נמצאה הפקדה חדשה עם הארנק המאומת וההערה שלך. "
                f"ודא שנשלח <code>{memo_for(msg.from_user.id)}</code> ונסה שוב.",
                parse_mode="HTML",
            )
            return

        lines = [
            f"• {item['amount_ton']:g} TON → {item['credits']:g} Credits"
            for item in credited
        ]
        total = sum(item["credits"] for item in credited)
        bot.reply_to(
            msg,
            "✅ הפקדות TON אומתו וזוכו:\n"
            + "\n".join(lines)
            + f"\n\nסה"כ: {total:g} Credits",
        )
