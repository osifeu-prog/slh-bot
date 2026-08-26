
LAST_EXEC = {}

def rate_limit(user_id):
    import time
    now = time.time()
    if user_id in LAST_EXEC and now - LAST_EXEC[user_id] < 2:
        return False
    LAST_EXEC[user_id] = now
    return True


import json, time
def audit_exec(user_id, cmd):
    log = json.load(open("state/exec_audit.json"))
    log.append({
        "user": user_id,
        "cmd": cmd,
        "time": time.time()
    })
    open("state/exec_audit.json","w").write(json.dumps(log,indent=2))


SAFE_COMMANDS = [
    'ls', 'cat', 'grep', 'python3', 'echo', 'head', 'tail'
]

def is_safe(cmd):
    for bad in ['rm', 'mv', 'chmod', 'chown', 'curl http', 'wget', 'scp', 'dd', 'kill', 'pkill']:
        if bad in cmd:
            return False
    return True

import subprocess
import os
from core.progress_tracker import progress_report

def register(bot, context):
    ADMIN_IDS = {int(os.getenv("ADMIN_ID", "8789977826"))}

    @bot.message_handler(commands=["exec"])
    def exec_cmd(m):
        if m.from_user.id not in ADMIN_IDS:
            bot.reply_to(m, "⛔ Admin only.")
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
                output = output[:4000] + "\n... truncated"

            bot.reply_to(
                m,
                "\n" + output + "\n\n" + progress_report()
            )

        except Exception as e:
            bot.reply_to(m, f"❌ Error: {e}")
