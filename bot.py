import telebot, json, subprocess, time

TOKEN = "8737037440:AAH0K-xMiW6P1qH-ps9FLpznj0AteAinj1c"
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(m):
    bot.reply_to(m, "🌟 ברוכים הבאים ל-SLH Learning! 🌟\n\n🎯 /join | /courses | /project | /referral")

@bot.message_handler(commands=['admin'])
def admin_panel(m):
    msg = "🔧 ADMIN PANEL\n\n"
    msg += "/diagnose\n/megadiag\n/exec <cmd>\n/backup\n/restart"
    bot.reply_to(m, msg)

@bot.message_handler(commands=['exec'])
def exec_cmd(m):
    if str(m.chat.id) != "8789977826":
        return bot.reply_to(m, "❌ Admin only")
    cmd = m.text.replace("/exec", "").strip()
    if not cmd:
        return bot.reply_to(m, "Usage: /exec <cmd>")
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        out = (r.stdout + r.stderr)[:4000] or "No output"
        bot.reply_to(m, f"💻 {cmd}\n{out}")
    except Exception as e:
        bot.reply_to(m, f"❌ {e}")

print("✅ Minimal bot ready")

# ========== LOAD EXTERNAL MODULES ==========
try:
    import learn_handlers; learn_handlers.register(bot)
    print("✅ learn_handlers loaded")
except Exception as e:
    print("⚠️ learn_handlers:", e)

try:
    import project_commands; project_commands.init(bot)
    print("✅ project_commands loaded")
except Exception as e:
    print("⚠️ project_commands:", e)

try:
    import smart_leaderboard; smart_leaderboard.init(bot)
    print("✅ smart_leaderboard loaded")
except Exception as e:
    print("⚠️ smart_leaderboard:", e)

try:
    import course_handlers; course_handlers.register_course_handlers(bot)
    print("✅ course_handlers loaded")
except Exception as e:
    print("⚠️ course_handlers:", e)

try:
    import logger_handler; logger_handler.init(bot)
    print("✅ logger_handler loaded (writing to message_log.txt)")
except Exception as e:
    print("⚠️ logger_handler:", e)

while True:
    try:
        bot.infinity_polling(timeout=20, long_polling_timeout=20)
    except Exception as e:
        print("Polling error:", e)
        time.sleep(5)
