import os
import time
import telebot
from pathlib import Path

UPLOAD_DIR = Path("state/uploads")
JOURNAL_FILE = Path("journal.json")

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def register(bot):
    @bot.message_handler(content_types=["document"])
    def handle_document(message):
        try:
            # Download file
            file_info = bot.get_file(message.document.file_id)
            downloaded = bot.download_file(file_info.file_path)

            # Save locally
            fname = message.document.file_name or f"doc_{int(time.time())}.txt"
            save_path = UPLOAD_DIR / fname

            with open(save_path, "wb") as f:
                f.write(downloaded)

            # Append to journal
            import json
            journal = []
            if JOURNAL_FILE.exists():
                try:
                    journal = json.loads(JOURNAL_FILE.read_text(encoding="utf-8"))
                except Exception:
                    journal = []

            journal.append({
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "from": str(message.from_user.id),
                "file_name": fname,
                "path": str(save_path)
            })

            JOURNAL_FILE.write_text(json.dumps(journal, ensure_ascii=False, indent=2))

            bot.reply_to(message, f"📎 הקובץ נשמר: {fname}\nנמצא בנתיב: state/uploads/{fname}")

        except Exception as e:
            bot.reply_to(message, f"❌ שגיאה בשמירת הקובץ: {e}")
