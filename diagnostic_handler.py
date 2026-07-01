import subprocess, os

DIAG_SCRIPT = os.path.expanduser("~/slh_clean/diag_scan.sh")

def init(bot):
    @bot.message_handler(commands=['diagnostic'])
    def diagnostic(m):
        if str(m.chat.id) not in ["8789977826"]:
            bot.reply_to(m, "❌ Admin only")
            return
        if not os.path.exists(DIAG_SCRIPT):
            bot.reply_to(m, "❌ diag_scan.sh not found")
            return
        try:
            result = subprocess.check_output(["bash", DIAG_SCRIPT], text=True, timeout=30)
            bot.reply_to(m, result[:4000])
        except subprocess.TimeoutExpired:
            bot.reply_to(m, "❌ Timeout")
        except Exception as e:
            bot.reply_to(m, f"❌ Error: {e}")
