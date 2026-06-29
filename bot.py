import telebot, json, subprocess, datetime

TOKEN = "8737037440:AAH0K-xMiW6P1qH-ps9FLpznj0AteAinj1c"
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(m):
    uid = str(m.chat.id)
    name = ""
    try:
        with open("db.json") as f:
            db = json.load(f)
        if uid in db.get("students", {}):
            name = db["students"][uid].get("name", "")
    except:
        pass
    msg = "🌟 **ברוכים הבאים ל-SLH Learning!** 🌟\n\n"
    if name:
        msg = f"נעים לראותך שוב, {name}!\n\n" + msg
    msg += "🎯 **הצעדים הראשונים:**\n"
    msg += "1️⃣ /join\n2️⃣ /courses\n3️⃣ /project create\n4️⃣ /myprogress\n5️⃣ /referral\n\n👥 **בואו נבנה יחד!**"
    bot.reply_to(m, msg, parse_mode="Markdown")

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

# Logger (no reply)
@bot.message_handler(func=lambda m: True)
def log_all(m):
    with open("message_log.txt", "a") as f:
        f.write(f"{datetime.datetime.now().isoformat()} | {m.chat.id} | {m.text}\n")

print("✅ Clean bot ready. Starting...")

import learn_handlers, project_commands, smart_leaderboard, welcome_handler, course_handlers, logger_handler
learn_handlers.register(bot)
project_commands.init(bot)
smart_leaderboard.init(bot)
welcome_handler.init(bot)
course_handlers.register_course_handlers(bot)
logger_handler.init(bot)
print("✅ All modules loaded")


@bot.message_handler(commands=['megadiag'])
def megadiag(m):
    import os, json, py_compile, subprocess, re, datetime, shutil
    lines = []
    lines.append("🩺 SLH MEGA DIAGNOSTIC")
    lines.append("="*30)
    # syntax
    for f in ["bot.py","learn_handlers.py","project_commands.py","smart_leaderboard.py","welcome_handler.py","course_handlers.py","logger_handler.py"]:
        if os.path.exists(f):
            try:
                py_compile.compile(f, doraise=True)
                lines.append(f"✅ {f}")
            except:
                lines.append(f"❌ {f}")
        else:
            lines.append(f"❌ {f} missing")
    # process
    r = subprocess.run(["pgrep","-af","python.*bot.py"], capture_output=True, text=True)
    lines.append("✅ Bot running" if r.stdout.strip() else "❌ No bot process")
    # commands
    with open("bot.py") as f:
        cmds = re.findall(r"commands=\['(\w+)'\]", f.read())
    lines.append(f"Commands ({len(set(cmds))}): {', '.join(sorted(set(cmds)))}")
    # db
    with open("db.json") as f:
        db = json.load(f)
    lines.append(f"Users: {len(db.get('users',{}))} | Students: {len(db.get('students',{}))} | Courses: {list(db.get('courses',{}).keys())}")
    lines.append(f"Admins: {db.get('admins',[])} | Token: {'Yes' if db.get('token') else 'No'}")
    # git
    r = subprocess.run(["git","log","--oneline","-3"], capture_output=True, text=True)
    lines.append("Last commits: " + r.stdout.strip().replace("\n", " | "))
    # cron
    r = subprocess.run(["crontab","-l"], capture_output=True, text=True)
    lines.append("Cron: " + ("Yes" if r.stdout.strip() else "No"))
    # disk
    r = subprocess.run(["du","-sh","."], capture_output=True, text=True)
    lines.append(f"Disk: {r.stdout.strip()}")
    bot.reply_to(m, "\n".join(lines))

bot.infinity_polling()
