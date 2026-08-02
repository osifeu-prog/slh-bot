import os, subprocess, shutil, datetime

BACKUP_DIR = os.path.expanduser("~/slh_clean/backups/junk")

def init(bot):
    # ----- סריקת זיכרון (Admin) -----
    @bot.message_handler(commands=['scan_junk'])
    def scan_junk(m):
        if str(m.chat.id) not in ["8789977826"]:
            bot.reply_to(m, "❌ Admin only"); return
        try:
            # find largest files/dirs in home (excluding .ollama and slh_clean)
            result = subprocess.check_output(
                "find ~ -maxdepth 4 -type f -not -path '*.ollama*' -not -path '*slh_clean*' -exec du -sh {} + 2>/dev/null | sort -rh | head -10",
                shell=True, text=True, timeout=15
            )
            if not result.strip():
                result = "לא נמצאו קבצים גדולים"
            bot.reply_to(m, f"📁 **Top 10 large files in home:**\n```\n{result[:3000]}\n```", parse_mode="Markdown")
        except subprocess.TimeoutExpired:
            bot.reply_to(m, "❌ Timeout")
        except Exception as e:
            bot.reply_to(m, f"❌ Error: {e}")

    # ----- גיבוי קובץ/תיקייה (Admin) -----
    @bot.message_handler(commands=['backup_junk'])
    def backup_junk(m):
        if str(m.chat.id) not in ["8789977826"]:
            bot.reply_to(m, "❌ Admin only"); return
        path = m.text.replace('/backup_junk', '').strip()
        if not path:
            bot.reply_to(m, "Usage: /backup_junk <path>")
            return
        full_path = os.path.expanduser(path)
        if not os.path.exists(full_path):
            bot.reply_to(m, f"❌ {path} not found")
            return
        try:
            os.makedirs(BACKUP_DIR, exist_ok=True)
            dest = os.path.join(BACKUP_DIR, os.path.basename(full_path) + "_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
            if os.path.isdir(full_path):
                shutil.copytree(full_path, dest)
            else:
                shutil.copy2(full_path, dest)
            bot.reply_to(m, f"✅ Backed up to {dest}")
        except Exception as e:
            bot.reply_to(m, f"❌ Error: {e}")

    # ----- מחיקה בטוחה (Admin) -----
    @bot.message_handler(commands=['clean_junk'])
    def clean_junk(m):
        if str(m.chat.id) not in ["8789977826"]:
            bot.reply_to(m, "❌ Admin only"); return
        path = m.text.replace('/clean_junk', '').strip()
        if not path:
            bot.reply_to(m, "Usage: /clean_junk <path>")
            return
        full_path = os.path.expanduser(path)
        if not os.path.exists(full_path):
            bot.reply_to(m, f"❌ {path} not found")
            return
        # safeguard: never delete slh_clean or .ollama
        if "slh_clean" in full_path or ".ollama" in full_path:
            bot.reply_to(m, "❌ Cannot delete project files or ollama")
            return
        try:
            if os.path.isdir(full_path):
                shutil.rmtree(full_path)
            else:
                os.remove(full_path)
            bot.reply_to(m, f"✅ Deleted {path}")
        except Exception as e:
            bot.reply_to(m, f"❌ Error: {e}")

    # ----- סריקת תלמיד (Sandbox) -----
    @bot.message_handler(commands=['my_junk'])
    def my_junk(m):
        uid = str(m.chat.id)
        try:
            result = subprocess.check_output(
                f"find /data/data/com.termux/files/home -maxdepth 4 -type f -user student_{uid} -exec du -sh {{}} + 2>/dev/null | sort -rh | head -5",
                shell=True, text=True, timeout=10
            )
            if not result.strip():
                result = "לא נמצאו קבצים"
            bot.reply_to(m, f"📁 **הקבצים הכי גדולים שלך:**\n```\n{result[:2000]}\n```", parse_mode="Markdown")
        except Exception as e:
            bot.reply_to(m, f"❌ Error: {e}")
