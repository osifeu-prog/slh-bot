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
        ok, out = run_gated(msg.from_user.id, parts[1], source="e", timeout=15)
        bot.reply_to(msg, out[:4000] or "(no output)")
