import telebot, json, os, time, datetime
import sys
sys.path.insert(0, "/data/data/com.termux/files/home/slh_clean")

TOKEN = os.environ.get("BOT_TOKEN") or "8737037440:AAH0K-xMiW6P1qH-ps9FLpznj0AteAinj1c"
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['test'])
def test_system(message):
    import py_compile, subprocess
    lines = []
    lines.append("✅ Bot alive")
    lines.append("✅ db.json" if os.path.exists("db.json") else "❌ db.json missing")
    r = subprocess.run(["pgrep","-af","python.*bot.py"], capture_output=True, text=True)
    lines.append(f"✅ PID: {r.stdout.strip()[:30]}")
    bot.reply_to(message, "\n".join(lines))

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "🌟 SLH OS v2.0 Ready!")

# טעינת מודולים
mods = [
    ("learn_handlers", lambda m: m.register(bot)),
    ("project_commands", lambda m: m.init(bot)),
    ("smart_leaderboard", lambda m: m.init(bot)),
    ("welcome_handler", lambda m: m.init(bot)),
    ("course_handlers", lambda m: m.register_course_handlers(bot)),
    ("logger_handler", lambda m: m.init(bot)),
]
for name, loader in mods:
    try:
        import importlib
        mod = importlib.import_module(name)
        loader(mod)
        print(f"✅ {name} loaded")
    except Exception as e:
        print(f"⚠️ {name} skipped: {e}")

print("🚀 Starting polling...")
bot.infinity_polling(none_stop=True, interval=0, timeout=20)
