from core.authority import is_owner

def _exchange_status_line():
    try:
        from core.system_checks import check_exchange
        result = check_exchange()
        gate = result.get("public_gate", "CLOSED")
        readiness = "READY" if result.get("public_ready") else "BLOCKED"
        verdict = result.get("verdict", "BLOCKED")
        if str(gate).strip().upper() == "CLOSED":
            return f"📈 Internal Exchange — CLOSED · readiness {readiness} is diagnostic only; trading remains closed."
        if (
            str(gate).strip().upper() == "OPEN"
            and str(verdict).strip().upper() == "OPEN"
            and result.get("public_ready") is True
            and result.get("ok") is True
            # The current main build has no financial-release field, so it
            # must never display OPEN until the reserve audit is integrated.
            and result.get("reserve_reconciliation_ok") is True
            and result.get("reserve_blocking_count") == 0
        ):
            return "📈 Internal Exchange — OPEN · canonical readiness checks PASS."
        return "📈 Internal Exchange — status unverified; treat trading as blocked."
    except Exception:
        return "📈 Internal Exchange — gate CLOSED · readiness UNKNOWN"


def register(bot):
    @bot.message_handler(commands=["faq"])
    def faq_cmd(msg):
        try:
            from core.faq_service import telegram_faq
            bot.reply_to(msg, telegram_faq())
        except Exception:
            bot.reply_to(msg, "FAQ לא זמין כרגע.")

    @bot.message_handler(commands=["help", "allcommands", "commands", "comands"])
    def help_cmd(msg):
        try:
            from core.command_catalog import render_public_help
            text = render_public_help("Me_ad_main")
        except Exception:
            text = "📘 מדריך SLH Spark לא זמין כרגע."
        text = _exchange_status_line() + "\n\n" + text
        bot.reply_to(msg, text)

 
    @bot.message_handler(commands=["opshelp"])
    def opshelp_cmd(msg):
        uid = getattr(getattr(msg, "from_user", None), "id", None)
        if not is_owner(uid):
            bot.reply_to(msg, "⛔ הפקודה זמינה לבעלים בלבד.")
            return
        try:
            from core.command_catalog import render_help
            text = render_help("Me_ad_main", limit=60)
        except Exception:
            text = "📘 קטלוג פקודות התפעול לא זמין כרגע."
        bot.reply_to(msg, _exchange_status_line() + "\n\n" + text)
