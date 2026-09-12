from core.exec_policy import is_owner, run_gated


def register(bot, context):

    @bot.message_handler(commands=["exec"])
    def exec_cmd(m):
        if not is_owner(m.from_user.id):
            bot.reply_to(m, "⛔️ Admin only.")
            return

        parts = m.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /exec <command>")
            return

        cmd = parts[1].strip()
        if cmd in ("alpha_status", "alpha_open"):
            try:
                from core.alpha_control_plane import evaluate, format_report, open_alpha

                if cmd == "alpha_status":
                    result = evaluate()
                    bot.reply_to(m, format_report(result))
                    return

                state = open_alpha(m.from_user.id)
                bot.reply_to(m, "🚀 ALPHA OPEN\n" + str(state))
                return
            except Exception as e:
                bot.reply_to(m, str(e))
                return

        ok, message = run_gated(m.from_user.id, cmd, source="exec")
        bot.reply_to(m, ("\n" + message) if ok else message)
