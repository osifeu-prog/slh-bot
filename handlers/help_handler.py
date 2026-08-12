def register(bot):
    @bot.message_handler(commands=["help"])
    def help_cmd(msg):
        cmds = []
        for h in bot.message_handlers:
            f = h.get("filters", {})
            c = f.get("commands", [])
            if c:
                cmds.append("/" + c[0])
        cmds = sorted(set(cmds))
        text = "🛟 SLH Commands\n\n" + "\n".join(cmds[:80])
        bot.reply_to(msg, text[:4000])
    print("✅ help handler registered (dynamic)")
