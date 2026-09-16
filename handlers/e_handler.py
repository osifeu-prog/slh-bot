from core.exec_policy import is_admin, run_audit, run_gated
from core.authority import is_owner


def register(bot):
    @bot.message_handler(commands=["e"])
    def e_cmd(msg):
        uid = msg.from_user.id
        parts = msg.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(msg, "Usage: /e <command>")
            return

        cmd = parts[1].strip()
        if cmd in ("alpha_status", "alpha_open", "alpha_state"):
            if not is_owner(uid):
                bot.reply_to(msg, "⛔️ OWNER only for alpha control-plane actions")
                return
            try:
                from core.alpha_control_plane import (
                    alpha_state,
                    evaluate,
                    format_report,
                    open_alpha,
                )

                if cmd == "alpha_status":
                    bot.reply_to(msg, format_report(evaluate()))
                    return
                if cmd == "alpha_state":
                    bot.reply_to(msg, "ALPHA STATE\n" + str(alpha_state()))
                    return

                state = open_alpha(uid)
                bot.reply_to(msg, "🚀 ALPHA OPEN\n" + str(state))
                return
            except Exception as exc:
                bot.reply_to(msg, str(exc))
                return

        if is_owner(uid):
            ok, out = run_gated(uid, cmd, source="e", timeout=15)
        elif is_admin(uid):
            ok, out = run_audit(uid, cmd, source="e_admin_audit", timeout=15)
        else:
            bot.reply_to(msg, "⛔️ Admin/Developer access required")
            return

        bot.reply_to(msg, out[:4000] or "(no output)")
