import subprocess as sp, os

def init(bot):
    @bot.message_handler(commands=['sandbox'])
    def sandbox(m):
        uid = str(m.chat.id)  # already matches the sandbox user
        if uid not in ["8789977826"] and uid != "8789977826":
            bot.reply_to(m, "❌ You can only run commands for yourself")
            return
        parts = m.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /sandbox <command>")
            return
        cmd = parts[1]
        # הגבלת פקודות (allowlist)
        allowed = ["whoami", "pwd", "ls", "echo", "mkdir", "touch", "cat", "python3", "bash"]
        first_word = cmd.split()[0]
        if first_word not in allowed:
            bot.reply_to(m, f"❌ Command not allowed: {first_word}")
            return
        # הרצה בתוך proot של התלמיד
        try:
            full_cmd = f"proot-distro login ubuntu -- bash -c 'su - student_{uid} -c \"{cmd} 2>&1 | grep -v \"proot warning\"\" '"
            result = sp.check_output(full_cmd, shell=True, text=True, timeout=15)
            bot.reply_to(m, result[:3000] or "(no output)")
        except sp.TimeoutExpired:
            bot.reply_to(m, "❌ Timeout")
        except Exception as e:
            bot.reply_to(m, f"❌ Error: {e}")
