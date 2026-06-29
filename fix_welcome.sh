#!/bin/bash
python3 << 'PYEOF'
import json, os

# Create welcome_handler.py safely
code = """import json

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
        msg = "\\uD83C\\uDF1F **\\u05D1\\u05E8\\u05D5\\u05DB\\u05D9\\u05DD \\u05D4\\u05D1\\u05D0\\u05D9\\u05DD \\u05DC-SLH Learning!** \\uD83C\\uDF1F\\n\\n"
        if name:
            msg += f"\\u05E0\\u05E2\\u05D9\\u05DD \\u05DC\\u05E8\\u05D0\\u05D5\\u05EA\\u05DA \\u05E9\\u05D5\\u05D1, {name}!\\n\\n"
        msg += "\\uD83C\\uDFAF **\\u05D4\\u05E6\\u05E2\\u05D3\\u05D9\\u05DD \\u05D4\\u05E8\\u05D0\\u05E9\\u05D5\\u05E0\\u05D9\\u05DD:**\\n"
        msg += "1\\uFE0F\\u20E3 \\u05D4\\u05D9\\u05E8\\u05E9\\u05DE\\u05D5: /join\\n"
        msg += "2\\uFE0F\\u20E3 \\u05E6\\u05E4\\u05D5 \\u05D1\\u05E7\\u05D5\\u05E8\\u05E1: /courses\\n"
        msg += "3\\uFE0F\\u20E3 \\u05E6\\u05E8\\u05D5 \\u05E4\\u05E8\\u05D5\\u05D9\\u05E7\\u05D8: /project create <\\u05E9\\u05DD>\\n"
        msg += "4\\uFE0F\\u20E3 \\u05D4\\u05D5\\u05E1\\u05D9\\u05E4\\u05D5 \\u05DE\\u05E9\\u05D9\\u05DE\\u05D5\\u05EA: /project task add <\\u05EA\\u05D9\\u05D0\\u05D5\\u05E8>\\n"
        msg += "5\\uFE0F\\u20E3 \\u05D1\\u05D3\\u05E7\\u05D5 \\u05D4\\u05EA\\u05E7\\u05D3\\u05DE\\u05D5\\u05EA: /myprogress\\n"
        msg += "6\\uFE0F\\u20E3 \\u05D4\\u05D6\\u05DE\\u05D9\\u05E0\\u05D5 \\u05D7\\u05D1\\u05E8\\u05D9\\u05DD: /referral\\n\\n"
        msg += "\\uD83D\\uDC65 **\\u05D1\\u05D5\\u05D0\\u05D5 \\u05E0\\u05D1\\u05E0\\u05D4 \\u05D9\\u05D7\\u05D3!**"
        bot.reply_to(m, msg, parse_mode="Markdown")
"""

with open("welcome_handler.py", "w", encoding="utf-8") as f:
    f.write(code)
print("✅ welcome_handler.py created")

# Update bot.py
with open("bot.py", "r") as f:
    bot_code = f.read()
if "import welcome_handler" not in bot_code:
    bot_code = bot_code.replace(
        "import learn_handlers, project_commands, smart_leaderboard",
        "import learn_handlers, project_commands, smart_leaderboard, welcome_handler"
    )
    bot_code = bot_code.replace(
        "smart_leaderboard.init(bot)",
        "smart_leaderboard.init(bot); welcome_handler.init(bot)"
    )
    with open("bot.py", "w") as f:
        f.write(bot_code)
    print("✅ bot.py updated")

# Restart
os.system("pkill -9 -f 'python.*bot.py'")
os.system("sleep 2")
os.system("./slh_daemon.sh")
print("✅ Bot restarted")
PYEOF
