import json

def init(bot):
    @bot.message_handler(commands=['start'])
    def send_welcome(m):
        uid = str(m.chat.id)
        name = ""
        try:
            with open("db.json") as f:
                db = json.load(f)
            if uid in db.get("students", {}):
                name = db["students"][uid].get("name", "")
        except:
            pass
        msg = "Welcome to SLH Learning!"
        if name:
            msg = f"Welcome back, {name}!\n\n" + msg
        msg += "\n\nCommands: /join, /courses, /project, /myprogress, /referral"
        bot.reply_to(m, msg)
