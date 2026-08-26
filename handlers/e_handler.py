import subprocess

def register(bot):
    @bot.message_handler(commands=["e"])
    def e_cmd(msg):
        parts = msg.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(msg, "Usage: /e <command>")
            return
        try:
            r = subprocess.run(
                parts[1],
                shell=True,
                capture_output=True,
                text=True,
                timeout=15
            )
            out = (r.stdout or "") + (r.stderr or "")
            bot.reply_to(msg, out[:4000] or "(no output)")
        except Exception as e:
            bot.reply_to(msg, f"Error: {e}")
