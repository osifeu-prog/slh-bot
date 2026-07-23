import json

def register(bot):
    @bot.message_handler(commands=['me'])
    def me_cmd(message):
        uid = str(message.from_user.id)
        try:
            with open('state/db.json') as f:
                users = json.load(f).get('users', {})
            user = users.get(uid, {})
            if not user:
                return bot.reply_to(message, "❌ לא נמצאה הרשמה. השתמש ב־/join")
            txt = f"👤 *פרופיל SLH*\n" \
                  f"• ID: {uid}\n" \
                  f"• שם: {user.get('name','לא ידוע')}\n" \
                  f"• תפקיד: {user.get('role','user')}\n" \
                  f"• הצטרף: {user.get('joined','לא ידוע')}"
            bot.reply_to(message, txt, parse_mode='Markdown')
        except Exception as e:
            bot.reply_to(message, f"שיאה: {e}")
