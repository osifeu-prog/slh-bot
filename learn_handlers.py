import json, datetime, os, uuid

DB_PATH = os.path.expanduser("~/slh_clean/db.json")
ADMIN_ID = "8789977826"
PAYMENT_WALLET = "EQDxsCK9f3ZgXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"   # <-- החלף בכתובת USDT שלך ב-TON

PAYMENT_WALLET = "EQDxsCK9f3ZgXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"   # ← החלף בכתובת USDT שלך
PAYMENT_AMOUNT = "60 USDT"

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
        name = m.text.strip()
        uid = str(m.chat.id)
        if not hasattr(process_name, 'temp'):
            process_name.temp = {}
        process_name.temp[uid] = {"name": name}
        sent = bot.reply_to(m, f"Nice to meet you, {name}!\nWhich group do you belong to? (e.g., 'Class A')")
        bot.register_next_step_handler(sent, process_group)

    def process_group(m):
        group = m.text.strip()
        uid = str(m.chat.id)
        process_name.temp[uid]["group"] = group
        sent = bot.reply_to(m, "What would you like to achieve? (type 'skip' to leave empty)")
        bot.register_next_step_handler(sent, process_goal)

    def process_goal(m):
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
            db["referral_codes"][uid] = code
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

    @bot.message_handler(commands=['pay'])
    def pay_info(m):
        uid = str(m.chat.id)
        db = load_db()
        student = db.get("students", {}).get(uid)
        if not student:
            bot.reply_to(m, "❌ Register first.")
            return
        if student.get("premium"):
            bot.reply_to(m, "✅ You are already a premium member.")
            return
        msg = f"💳 **Premium Access – {PAYMENT_AMOUNT}**\n"
        msg += f"Send exactly {PAYMENT_AMOUNT} (USDT on TON network) to:\n`{PAYMENT_WALLET}`\n"
        msg += "After payment, send the transaction hash here or contact the admin.\n"
        msg += "Once verified, you'll get full course access and your referral link."
        bot.reply_to(m, msg, parse_mode="Markdown")

    @bot.message_handler(commands=['activate'])
    def activate_user(m):
        if str(m.chat.id) != ADMIN_ID:
            bot.reply_to(m, "❌ Admin only.")
            return
        args = m.text.split()
        if len(args) < 2:
            bot.reply_to(m, "❌ Usage: /activate <user_id>")
            return
        target_uid = args[1]
        db = load_db()
        student = db.get("students", {}).get(target_uid)
        if not student:
            bot.reply_to(m, "❌ User not registered.")
            return
        student["premium"] = True
        referrer = db.get("referred_by", {}).get(target_uid)
        if referrer:
            db.setdefault("commissions", {}).setdefault(referrer, 0)
            db["commissions"][referrer] += 85
            db.setdefault("commissions", {}).setdefault(ADMIN_ID, 0)
            db["commissions"][ADMIN_ID] += 15
        save_db(db)
        bot.reply_to(m, f"✅ User {target_uid} activated. Premium access granted.")

    @bot.message_handler(commands=['commission'])
    def check_commission(m):
        uid = str(m.chat.id)
        db = load_db()
        comm = db.get("commissions", {}).get(uid, 0)
        bot.reply_to(m, f"💰 Your total commission: {comm} USDT")

    @bot.message_handler(commands=['withdraw'])
    def withdraw_commission(m):
        bot.reply_to(m, "📤 Withdrawal request sent. Admin will process it.")

    def is_premium(uid):
        db = load_db()
        return db.get("students", {}).get(uid, {}).get("premium", False)

    @bot.message_handler(commands=['courses'])
    def list_courses(m):
        uid = str(m.chat.id)
        if not is_premium(uid):
            bot.reply_to(m, f"🔒 Premium content. Use /pay to unlock for {PAYMENT_AMOUNT}.")
            return
        db = load_db()
        courses = db.get("courses", {})
        if not courses:
            bot.reply_to(m, "📭 No courses yet.")
            return
        msg = "📚 **Courses:**\n"
        for cid, cdata in courses.items():
            msg += f"• `{cid}` – {cdata['title']}\n"
        bot.reply_to(m, msg, parse_mode="Markdown")

    @bot.message_handler(commands=['task'])
    def show_task(m):
        uid = str(m.chat.id)
        if not is_premium(uid):
            bot.reply_to(m, "🔒 Premium required. Use /pay to unlock.")
            return
        args = m.text.split(maxsplit=2)
        if len(args) < 3:
            bot.reply_to(m, "❌ Use: /task <course> <task_id>")
            return
        cid, tid = args[1], args[2]
        db = load_db()
        course = db.get("courses", {}).get(cid)
        if not course or tid not in course.get("tasks", {}):
            bot.reply_to(m, "❌ Course or task not found.")
            return
        desc = course["tasks"][tid].get("description", "No description")
        bot.reply_to(m, f"📌 **{course['title']}** – Task `{tid}`:\n{desc}", parse_mode="Markdown")

    @bot.message_handler(commands=['submit'])
    def submit_task(m):
        uid = str(m.chat.id)
        if not is_premium(uid):
            bot.reply_to(m, "🔒 Premium required.")
            return
        args = m.text.split(maxsplit=3)
        if len(args) < 4:
            bot.reply_to(m, "❌ Use: /submit <course> <task_id> <answer>")
            return
        cid, tid, answer = args[1], args[2], args[3]
        db = load_db()
        course = db.get("courses", {}).get(cid)
        if not course or tid not in course.get("tasks", {}):
            bot.reply_to(m, "❌ Course or task not found.")
            return
        now = datetime.datetime.now().isoformat()
        db.setdefault("progress", {}).setdefault(uid, {}).setdefault(cid, {"completed": [], "submissions": {}, "score": 0})
        db["progress"][uid][cid]["submissions"][tid] = {"answer": answer, "timestamp": now, "status": "pending", "feedback": ""}
        add_points(uid, 5)
        save_db(db)
        bot.reply_to(m, f"✅ Submission received for `{tid}` in `{cid}`. +5 points\nStatus: pending review.")

    @bot.message_handler(commands=['add_course'])
    def add_course(m):
        if str(m.chat.id) != ADMIN_ID:
            bot.reply_to(m, "❌ Admin only.")
            return
        args = m.text.split(maxsplit=2)
        if len(args) < 3:
            bot.reply_to(m, "❌ Use: /add_course <course_id> <title>")
            return
        cid, title = args[1], args[2]
        db = load_db()
        if cid in db.get("courses", {}):
            bot.reply_to(m, "⚠️ Course ID already exists.")
            return
        db.setdefault("courses", {})[cid] = {"title": title, "tasks": {}}
        save_db(db)
        bot.reply_to(m, f"✅ Course `{cid}` – **{title}** added.", parse_mode="Markdown")

    @bot.message_handler(commands=['add_task'])
    def add_task(m):
        if str(m.chat.id) != ADMIN_ID:
            bot.reply_to(m, "❌ Admin only.")
            return
        args = m.text.split(maxsplit=3)
        if len(args) < 4:
            bot.reply_to(m, "❌ Use: /add_task <course_id> <task_id> <description>")
            return
        cid, tid, desc = args[1], args[2], args[3]
        db = load_db()
        if cid not in db.get("courses", {}):
            bot.reply_to(m, "❌ Course not found.")
            return
        db["courses"][cid].setdefault("tasks", {})[tid] = {"description": desc}
        save_db(db)
        bot.reply_to(m, f"✅ Task `{tid}` added to `{cid}`.")

    @bot.message_handler(commands=['review'])
    def review_submissions(m):
        if str(m.chat.id) != ADMIN_ID:
            bot.reply_to(m, "❌ Admin only.")
            return
        args = m.text.split()
        if len(args) < 3:
            bot.reply_to(m, "❌ Use: /review <student_id> <course_id>")
            return
        sid, cid = args[1], args[2]
        db = load_db()
        progress = db.get("progress", {}).get(sid, {}).get(cid)
        if not progress:
            bot.reply_to(m, "❌ No submissions found.")
            return
        subs = progress.get("submissions", {})
        if not subs:
            bot.reply_to(m, "📭 No submissions.")
            return
        msg = f"📋 Submissions by {sid} in {cid}:\n"
        for tid, data in subs.items():
            status = data.get("status", "pending")
            answer = data.get("answer", "")[:50] + ("..." if len(data.get("answer",""))>50 else "")
            msg += f"• {tid}: \"{answer}\" [{status}]\n"
        msg += "\nUse /approve <student_id> <course_id> <task_id>"
        bot.reply_to(m, msg)

    @bot.message_handler(commands=['approve'])
    def approve_task(m):
        if str(m.chat.id) != ADMIN_ID:
            bot.reply_to(m, "❌ Admin only.")
            return
        args = m.text.split()
        if len(args) < 4:
            bot.reply_to(m, "❌ Use: /approve <student_id> <course_id> <task_id>")
            return
        sid, cid, tid = args[1], args[2], args[3]
        db = load_db()
        try:
            sub = db["progress"][sid][cid]["submissions"][tid]
        except KeyError:
            bot.reply_to(m, "❌ Submission not found.")
            return
        sub["status"] = "approved"
        comp = db["progress"][sid][cid].setdefault("completed", [])
        if tid not in comp:
            comp.append(tid)
        add_points(sid, 20)
        save_db(db)
        bot.reply_to(m, f"✅ Approved: {sid} – {tid} +20 points")

    @bot.message_handler(commands=['leaderboard'])
    def leaderboard(m):
        db = load_db()
        users = db.get("users", {})
        if not users:
            bot.reply_to(m, "📭 No users yet.")
            return
        sorted_users = sorted(users.items(), key=lambda x: x[1].get("points", 0), reverse=True)
        msg = "🏆 **Leaderboard:**\n"
        for i, (uid, data) in enumerate(sorted_users[:10], 1):
            name = db.get("students", {}).get(uid, {}).get("name", uid)
            points = data.get("points", 0)
            msg += f"{i}. {name} – {points} pts\n"
        bot.reply_to(m, msg, parse_mode="Markdown")

    @bot.message_handler(commands=['toncard'])
    def toncard(m):
        bot.reply_to(m, "🪪 TON Card feature is under development. Check back soon!")
