import json, datetime, os, uuid

DB_PATH = "state/db.json"

def load_db():
    with open(DB_PATH) as f:
        return json.load(f)

def save_db(db):
    with open(DB_PATH, "w") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

def add_points(uid, points):
    db = load_db()
    db.setdefault("users", {}).setdefault(uid, {"points": 0})
    db["users"][uid]["points"] = db["users"][uid].get("points", 0) + points
    save_db(db)

def register(bot):
    @bot.message_handler(commands=['join'])
    def start_join(m):
        uid = str(m.chat.id)
        db = load_db()
        if uid in db.get("students", {}):
            bot.reply_to(m, "⚠️ Already registered. Use /myprogress.")
            return
        sent = bot.reply_to(m, "👋 Welcome to SLH Learning!\nWhat is your full name?")
        bot.register_next_step_handler(sent, process_name)
    def process_name(m):
        if m.text.startswith("/"):
            bot.process_new_messages([m])
            return
        name = m.text.strip()
        uid = str(m.chat.id)
        if not hasattr(process_name, 'temp'):
            process_name.temp = {}
        process_name.temp[uid] = {"name": name}
        sent = bot.reply_to(m, f"Nice to meet you, {name}!\nWhich group do you belong to? (e.g., 'Class A')")
        bot.register_next_step_handler(sent, process_group)

    def process_group(m):
        if m.text.startswith("/"):
            bot.process_new_messages([m])
            return
        group = m.text.strip()
        uid = str(m.chat.id)
        process_name.temp[uid]["group"] = group
        sent = bot.reply_to(m, "What would you like to achieve? (type 'skip' to leave empty)")
        bot.register_next_step_handler(sent, process_goal)

    def process_goal(m):
        if m.text.startswith("/"):
            bot.process_new_messages([m])
            return
        goal = m.text.strip()
        uid = str(m.chat.id)
        data = process_name.temp.pop(uid)
        if goal.lower() == 'skip':
            goal = ""
        db = load_db()
        referred_by = db.get("referred_by", {}).get(uid)
        db.setdefault("students", {})[uid] = {
            "name": data["name"],
            "group": data["group"],
            "goal": goal,
            "registered": datetime.datetime.now().isoformat(),
            "premium": False,
            "referral_code": None,
            "referred_by": referred_by
        }
        add_points(uid, 10)
        save_db(db)
        msg = f"✅ Registered: {data['name']} ({data['group']})\n"
        if not referred_by:
            msg += "🔗 Do you have a referral code? Use /usereferral <code>"
        bot.reply_to(m, msg)

    @bot.message_handler(commands=['register'])
    def register_student(m):
        args = m.text.split(maxsplit=2)
        if len(args) < 3:
            bot.reply_to(m, "❌ Use: /register <name> <group>")
            return
        name, group = args[1], args[2]
        uid = str(m.chat.id)
        db = load_db()
        if uid in db["students"]:
            bot.reply_to(m, "⚠️ Already registered.")
            return
        db["students"][uid] = {"name": name, "group": group, "registered": datetime.datetime.now().isoformat()}
        add_points(uid, 10)
        save_db(db)
        bot.reply_to(m, f"✅ Registered: {name} ({group}) +10 points")

    @bot.message_handler(commands=['courses'])
    def list_courses(m):
        db = load_db()
        courses = db.get("courses", {})
        if not courses:
            bot.reply_to(m, "📭 No courses yet.")
            return
        msg = "📚 **Courses:**\n"
        for cid, cdata in courses.items():
            msg += f"• `{cid}` – {cdata['title']}\n"
        bot.reply_to(m, msg, parse_mode="Markdown")

    def my_progress(m):
        uid = str(m.chat.id)
        db = load_db()
        student = db.get("students", {}).get(uid)
        if not student:
            bot.reply_to(m, "❌ Register first: /register <name> <group>")
            return
        progress = db.get("progress", {}).get(uid, {})
        points = db.get("users", {}).get(uid, {}).get("points", 0)
        msg = f"📊 Progress of {student['name']} (Points: {points}):\n"
        for cid, pdata in progress.items():
            course = db.get("courses", {}).get(cid, {})
            title = course.get("title", cid)
            completed = len(pdata.get("completed", []))
            total = len(course.get("tasks", {}))
            submitted = len(pdata.get("submissions", {}))
            msg += f"• {title}: {submitted}/{total} submitted, {completed} approved\n"
        bot.reply_to(m, msg)

    @bot.message_handler(commands=['referral'])
    def my_referral(m):
        uid = str(m.chat.id)
        db = load_db()
        student = db.get("students", {}).get(uid)
        if not student:
            bot.reply_to(m, "❌ Register first.")
            return
        if not student.get("referral_code"):
            code = uid[:4] + str(uuid.uuid4())[:6]
            student["referral_code"] = code
            db.setdefault("referral_codes", {})[uid] = code
            save_db(db)
        bot.reply_to(m, f"🔗 Your referral link:\nhttps://t.me/SLH_OS_Bot?start={student['referral_code']}\n\nShare this link with friends. When they register and pay, you earn 85% commission!")

    @bot.message_handler(commands=['usereferral'])
    def use_referral(m):
        args = m.text.split(maxsplit=1)
        if len(args) < 2:
            bot.reply_to(m, "❌ Usage: /usereferral <code>")
            return
        code = args[1]
        uid = str(m.chat.id)
        db = load_db()
        owner = None
        for id_, ref_code in db.get("referral_codes", {}).items():
            if ref_code == code:
                owner = id_
                break
        if not owner:
            bot.reply_to(m, "❌ Invalid referral code.")
            return
        if uid == owner:
            bot.reply_to(m, "❌ You cannot refer yourself.")
            return
        db.setdefault("referred_by", {})[uid] = owner
        save_db(db)
        bot.reply_to(m, "✅ Referral code applied! You will be linked to your referrer when you pay.")
