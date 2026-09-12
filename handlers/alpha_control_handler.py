from core.exec_policy import is_owner
from core.alpha_control_plane import evaluate, format_report, open_alpha, alpha_state


def register(bot, context=None):
    @bot.message_handler(commands=["alpha_status"])
    def alpha_status_cmd(m):
        if not is_owner(m.from_user.id):
            bot.reply_to(m, "⛔️ Owner only.")
            return
        bot.reply_to(m, format_report(evaluate()))

    @bot.message_handler(commands=["alpha_open"])
    def alpha_open_cmd(m):
        if not is_owner(m.from_user.id):
            bot.reply_to(m, "⛔️ Owner only.")
            return
        try:
            state = open_alpha(m.from_user.id)
            bot.reply_to(m, "🚀 ALPHA OPEN\n" + str(state))
        except Exception as e:
            bot.reply_to(m, str(e))

    @bot.message_handler(commands=["alpha_state"])
    def alpha_state_cmd(m):
        if not is_owner(m.from_user.id):
            bot.reply_to(m, "⛔️ Owner only.")
            return
        bot.reply_to(m, "ALPHA STATE\n" + str(alpha_state()))
