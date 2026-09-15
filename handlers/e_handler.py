from core.exec_policy import run_gated, run_audit
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

        # Alpha state transitions remain OWNER-only. Diagnostics may be
        # available to admins/developers, but opening alpha may not.
        if cmd in ("alpha_status", "alpha_open", "alpha_state"):
            if not is_owner(uid):
                bot.reply_to(msg, "⛔️ Owner only for alpha control.")
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

        # Owner keeps the existing gated execution path. Admins/developers
        # receive the same bounded read-only audit surface as /exec.
        if is_owner(uid):
            ok, out = run_gated(uid, cmd, source="e", timeout=15)
        else:
            ok, out = run_audit(uid, cmd, source="e_admin_audit", timeout=15)

        bot.reply_to(msg, out[:4000] or "(no output)")
