import datetime

def init(bot):
    @bot.message_handler(func=lambda m: True)
    def log_everything(message):
        uid = str(message.chat.id)
        text = message.text or "[no text]"
        timestamp = datetime.datetime.now().isoformat()
        entry = f"{timestamp} | {uid} | {text}\n"
        with open("message_log.txt", "a", encoding="utf-8") as logfile:
            logfile.write(entry)
        # No reply - just log
