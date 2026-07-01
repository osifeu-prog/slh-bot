import json

def init(bot):
    @bot.message_handler(commands=['broadcast'])
    def broadcast(m):
        if str(m.chat.id) not in ["8789977826"]: # admin check
            bot.reply_to(m, "❌ Admin only")
            return
        parts = m.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /broadcast <message>")
            return
        msg_text = parts[1]
        try:
            with open("db.json") as f: db = json.load(f)
        except:
            bot.reply_to(m, "❌ DB error")
            return
        count = 0
        for uid in db.get("students", {}):
            try:
                bot.send_message(uid, "📢 " + msg_text)
                count += 1
            except:
                pass
        bot.reply_to(m, f"✅ נשלח ל־{count} תלמידים")
