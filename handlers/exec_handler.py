from core.exec_policy import is_owner, is_admin, run_gated, run_audit


def register(bot, context):

    @bot.message_handler(commands=["exec"])
    def exec_cmd(m):
        uid = m.from_user.id
        parts = m.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /exec <command>")
            return

        cmd = parts[1].strip()

        # Alpha state transitions remain OWNER-only.
        if cmd in ("alpha_status", "alpha_open"):
            if not is_owner(uid):
                bot.reply_to(m, "⛔️ Owner only.")
                return
            try:
                from core.alpha_control_plane import evaluate, format_report, open_alpha

                if cmd == "alpha_status":
                    result = evaluate()
                    bot.reply_to(m, format_report(result))
                    return

                state = open_alpha(uid)
                bot.reply_to(m, "🚀 ALPHA OPEN\n" + str(state))
                return
            except Exception as e:
                bot.reply_to(m, str(e))
                return

        # ADMIN identities receive read-only diagnostics, never arbitrary shell.
        if is_admin(uid) and not is_owner(uid):
            ok, message = run_audit(uid, cmd, source="exec_admin_audit")
        else:
            ok, message = run_gated(uid, cmd, source="exec")

        bot.reply_to(m, ("\n" + message) if ok else message)
