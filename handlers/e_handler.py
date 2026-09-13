from core.exec_policy import run_gated
from core.authority import is_owner


def register(bot):
    @bot.message_handler(commands=["e"])
    def e_cmd(msg):
        if not is_owner(msg.from_user.id):
            bot.reply_to(msg, "⛔️ OWNER only")
            return
        parts = msg.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(msg, "Usage: /e <command>")
            return

        cmd = parts[1].strip()
        if cmd in ("alpha_status", "alpha_open", "alpha_state"):
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

                state = open_alpha(msg.from_user.id)
                bot.reply_to(msg, "🚀 ALPHA OPEN\n" + str(state))
                return
            except Exception as exc:
                bot.reply_to(msg, str(exc))
                return

        ok, out = run_gated(msg.from_user.id, cmd, source="e", timeout=15)
        bot.reply_to(msg, out[:4000] or "(no output)")
