import json, datetime, os

DB_PATH = os.path.expanduser("~/slh_clean/db.json")

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
        db.setdefault("students", {})[uid] = {
            "name": data["name"],
            "group": data["group"],
            "goal": goal,
            "registered": datetime.datetime.now().isoformat()
        }
        add_points(uid, 10)
        save_db(db)
        bot.reply_to(m, f"✅ Registered: {data['name']} ({data['group']})\n🎯 Goal: {goal if goal else 'Not specified'}\n💰 +10 points. Use /courses.")

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

    @bot.message_handler(commands=['task'])
    def show_task(m):
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
        args = m.text.split(maxsplit=3)
        if len(args) < 4:
            bot.reply_to(m, "❌ Use: /submit <course> <task_id> <answer>")
            return
        cid, tid, answer = args[1], args[2], args[3]
        uid = str(m.chat.id)
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

    @bot.message_handler(commands=['myprogress'])
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

    @bot.message_handler(commands=['add_course'])
    def add_course(m):
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
