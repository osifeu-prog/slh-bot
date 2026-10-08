def _exchange_status_line():
    try:
        from core.system_checks import check_exchange
        result = check_exchange()
        gate = result.get("public_gate", "CLOSED")
        readiness = "READY" if result.get("public_ready") else "BLOCKED"
        verdict = result.get("verdict", "BLOCKED")
        return f"📈 Internal Exchange — gate {gate} · readiness {readiness} · {verdict}"
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
            from core.command_catalog import render_help
            text = render_help("Me_ad_main", limit=60)
        except Exception:
            text = "📘 Runtime Command Catalog לא זמין כרגע."
        text = _exchange_status_line() + "\n\n" + text
        bot.reply_to(msg, text)
