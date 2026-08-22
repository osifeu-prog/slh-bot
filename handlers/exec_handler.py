import subprocess
import os
import json
from pathlib import Path
from datetime import datetime
from core.progress_tracker import progress_report

def register(bot, context):
    ADMIN_IDS = {int(os.getenv("ADMIN_ID", "8789977826"))}

    @bot.message_handler(commands=["exec"])
    def exec_cmd(m):
        if m.from_user.id not in ADMIN_IDS:
            
            # --- EXEC LOGGING ---
            try:
                import json, time
                log_path = Path("state/exec_log.json")
                logs = []
                if log_path.exists():
                    logs = json.loads(log_path.read_text(encoding="utf-8"))
                logs.append({
                    "cmd": cmd,
                    "output": output,
                    "ts": time.time()
                })
                log_path.write_text(json.dumps(logs, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception as e:
                print("EXEC_LOG_ERROR:", e)
            # --- END LOGGING ---

            
            # --- EXEC LOGGING ---
            try:
                import json, time
                log_path = Path("state/exec_log.json")
                logs = []
                if log_path.exists():
                    logs = json.loads(log_path.read_text(encoding="utf-8"))
                logs.append({
                    "cmd": cmd,
                    "output": output,
                    "ts": time.time()
                })
                log_path.write_text(json.dumps(logs, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception as e:
                print("EXEC_LOG_ERROR:", e)
            # --- END LOGGING ---

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

            # שמירת EXEC אחרון לזיכרון תפעולי
            try:
                db_path = Path("state/db.json")
                db = json.loads(db_path.read_text(encoding="utf-8"))

                db["last_exec_output"] = {
                    "command": cmd,
                    "output": output,
                    "ts": datetime.now().isoformat()
                }

                db_path.write_text(
                    json.dumps(db, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )

            except Exception as e:
                print("SAVE_EXEC_OUTPUT_ERROR:", e)

            bot.reply_to(
                m,
                "\n" + output + "\n\n" + progress_report()
            )

        except Exception as e:
            bot.reply_to(m, f"❌ Error: {e}")
