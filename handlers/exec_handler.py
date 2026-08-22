import subprocess
import os
from core.progress_tracker import progress_report

def register(bot, context):
    ADMIN_IDS = {int(os.getenv("ADMIN_ID", "8789977826"))}

    @bot.message_handler(commands=["exec"])
    def exec_cmd(m):
        if m.from_user.id not in ADMIN_IDS:
            bot.reply_to(m, "⛔️ Admin only.")
            return

        parts = m.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /exec <command>")
            return

        cmd = parts[1]

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=15
            )

            output = result.stdout + result.stderr

            if len(output) > 4000:
                output = output[:4000] + "
... truncated"

            bot.reply_to(
                m,
                f"
{output}
" + "

" + progress_report()
            )

        except Exception as e:
            bot.reply_to(m, f"❌ Error: {e}")
