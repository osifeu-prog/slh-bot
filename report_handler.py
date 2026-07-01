import json, os, subprocess, datetime

JOURNAL_FILE = os.path.expanduser("~/slh_clean/state/journal.json")

def load_journal():
    if os.path.exists(JOURNAL_FILE):
        with open(JOURNAL_FILE) as f:
            return json.load(f)
    return []

def save_journal(entries):
    os.makedirs(os.path.dirname(JOURNAL_FILE), exist_ok=True)
    with open(JOURNAL_FILE, "w") as f:
        json.dump(entries, f, indent=2)

def init(bot):
    # ----- דו"ח אישי יומי -----
    @bot.message_handler(commands=['myreport'])
    def my_report(m):
        uid = str(m.chat.id)
        try:
            with open(os.path.expanduser("~/slh_clean/db.json")) as f:
                db = json.load(f)
            student = db.get("students", {}).get(uid)
            if not student:
                bot.reply_to(m, "❌ לא רשום. /join")
                return
            name = student.get("name", "ללא שם")
            course = student.get("courses", {}).get("bitcoin_mastery", {})
            progress = course.get("progress", 0)
            stage = course.get("current_stage", 1)
            points = student.get("points", 0)
            refs = student.get("referral_count", 0)
            active_proj = db.get("active_projects", {}).get(uid, "אין")
            completed = student.get("completed_tasks", [])
            report = (
                f"☀️ **הדו\"ח היומי של {name}**\n"
                f"📚 קורס: {progress}% (שלב {stage})\n"
                f"📁 פרויקט פעיל: {active_proj}\n"
                f"🔗 הפניות: {refs}\n"
                f"⭐ נקודות: {points}\n"
                f"✅ משימות שהושלמו: {len(completed)}\n"
                f"🕒 {datetime.date.today()}"
            )
        except Exception as e:
            report = f"❌ Error: {e}"
        bot.reply_to(m, report)

    # ----- דו"ח בוקר (Admin) -----
    @bot.message_handler(commands=['morning_report'])
    def morning_report(m):
        if str(m.chat.id) not in ["8789977826"]:
            bot.reply_to(m, "❌ Admin only"); return
        try:
            with open(os.path.expanduser("~/slh_clean/db.json")) as f:
                db = json.load(f)
            students = db.get("students", {})
            total_points = sum(s.get("points",0) for s in students.values())
            disk = subprocess.check_output("df -h ~ | tail -1 | awk '{print $5}'", shell=True, text=True).strip()
            ollama = "✅" if os.popen("pgrep -f 'ollama serve'").read().strip() else "❌"
            bot_status = "✅" if os.popen("pgrep -af bot_stable.py").read().strip() else "❌"
            report = (
                f"☀️ **Morning Report** – {datetime.date.today()}\n"
                f"👥 תלמידים: {len(students)} | ⭐ נקודות: {total_points}\n"
                f"🧠 Ollama: {ollama}\n"
                f"💾 דיסק: {disk}\n"
                f"🤖 בוט: {bot_status}"
            )
        except Exception as e:
            report = f"❌ Error: {e}"
        bot.reply_to(m, report)

    # ----- דו"ח ערב (Admin) -----
    @bot.message_handler(commands=['evening_report'])
    def evening_report(m):
        if str(m.chat.id) not in ["8789977826"]:
            bot.reply_to(m, "❌ Admin only"); return
        try:
            backups = os.popen("ls -lt ~/slh_clean/backups/*.json ~/slh_clean/backups/*.tar.gz 2>/dev/null | head -3").read()
            disk = subprocess.check_output("df -h ~ | tail -1 | awk '{print $5}'", shell=True, text=True).strip()
            with open(os.path.expanduser("~/slh_clean/db.json")) as f:
                db = json.load(f)
            students = len(db.get("students",{}))
            agents = len(db.get("agents",{}))
            report = (
                f"🌙 **Evening Report** – {datetime.date.today()}\n"
                f"👥 תלמידים: {students} | 🤖 סוכנים: {agents}\n"
                f"💾 דיסק: {disk}\n"
                f"📦 גיבויים אחרונים:\n{backups or 'אין'}"
            )
        except Exception as e:
            report = f"❌ Error: {e}"
        bot.reply_to(m, report)

    # ----- יומן אישי (Admin) -----
    @bot.message_handler(commands=['journal'])
    def journal_write(m):
        if str(m.chat.id) not in ["8789977826"]:
            bot.reply_to(m, "❌ Admin only"); return
        text = m.text.replace('/journal', '').strip()
        if not text:
            bot.reply_to(m, "Usage: /journal <text>")
            return
        entries = load_journal()
        entries.append({"time": str(datetime.datetime.now()), "text": text})
        save_journal(entries)
        bot.reply_to(m, "✅ Journal updated")

    # ----- קריאת יומן (Admin) -----
    @bot.message_handler(commands=['journal_read'])
    def journal_read(m):
        if str(m.chat.id) not in ["8789977826"]:
            bot.reply_to(m, "❌ Admin only"); return
        entries = load_journal()
        if not entries:
            bot.reply_to(m, "📭 Journal empty")
        else:
            msg = "\n".join([f"🕒 {e['time']}\n{e['text']}\n" for e in entries[-10:]])
            bot.reply_to(m, msg)
