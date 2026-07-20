import json, datetime, os

FEEDBACK_FILE = "state/feedback.json"

def register(bot):
    @bot.message_handler(commands=['feedback'])
    def feedback_cmd(m):
        text = m.text.replace('/feedback', '').strip()
        if not text:
            bot.reply_to(m, "📝 שלח /feedback <הטקסט שלך>")
            return
        
        entry = {
            "user_id": m.from_user.id,
            "time": datetime.datetime.now().isoformat(),
            "text": text
        }
        
        try:
            with open(FEEDBACK_FILE, 'r') as f:
                data = json.load(f)
        except:
            data = []
        
        data.append(entry)
        
        with open(FEEDBACK_FILE, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        bot.reply_to(m, "🙏 תודה על הפידבק! אנחנו קוראים כל תגובה.")
