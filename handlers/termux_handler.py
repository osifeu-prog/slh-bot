import os
from admin_utils import is_admin

def register(bot):
    @bot.message_handler(commands=['termux'])
    def termux_cmd(m):
        if not is_admin(m):
            bot.reply_to(m, "❌ Admin only")
            return
        # גרסה בטוחה – מחזירה מידע על ה‑Container
        # (זו גרסת דמה, לא Remote Control מלא)
        bot.reply_to(m, f"Python: {os.sys.version}\ncwd: {os.getcwd()}")
