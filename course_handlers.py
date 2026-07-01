import json, os

DB_PATH = "state/db.json"

def load_db():
    with open(DB_PATH) as f:
        return json.load(f)

def save_db(db):
    with open(DB_PATH, "w") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

def register_course_handlers(bot):
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
        with open("config.json") as f:
            cfg = json.load(f)
        wallet = cfg.get('TON_WALLET', 'UQCd7XHWGj06cBLlWW_DZUN3TWMGr_oWoVy0G0LkC14gQklj')
        msg = f"💳 **Premium Access – {cfg.get('COURSE_PRICE_USDT', 60)} USDT**\n"
        msg += f"Send exactly {cfg.get('COURSE_PRICE_USDT', 60)} USDT (TON network) to:\n`{wallet}`\n"
        msg += "After payment, send the transaction hash here or contact the admin.\n"
        msg += "Once verified, you'll get full course access and your referral link."
        bot.reply_to(m, msg, parse_mode="Markdown")

    @bot.message_handler(commands=['activate'])
    def activate_user(m):
        if str(m.chat.id) != "8789977826":
            bot.reply_to(m, "❌ Admin only.")
            return
        args = m.text.split()
        if len(args) < 3:
            bot.reply_to(m, "❌ Usage: /activate <user_id> <course_id>")
            return
        target_uid = args[1]
        course_id = args[2]
        db = load_db()
        student = db.get("students", {}).get(target_uid)
        if not student:
            bot.reply_to(m, "❌ User not registered.")
            return
        if "courses" not in student:
            student["courses"] = {}
        student["courses"][course_id] = {"paid": True, "progress": 0}
        save_db(db)
        bot.reply_to(m, f"✅ User {target_uid} activated for {course_id}")

    @bot.message_handler(commands=['course'])
    def course_command(m):
        db = load_db()
        uid = str(m.chat.id)
        parts = m.text.split()
        if len(parts) < 2:
            course_id = "bitcoin_mastery"
            course = db.get("courses", {}).get(course_id)
            if not course:
                bot.reply_to(m, "📭 No course found.")
                return
            msg = f"📚 **{course['title']}**\n\n"
            for tid, tdata in course["tasks"].items():
                enrolled = db.get("students", {}).get(uid, {}).get("courses", {}).get(course_id, {})
                if enrolled.get("paid"):
                    status = "🔓"
                else:
                    status = "🔒" if tdata.get("required_refs", 0) > 0 else "🔓"
                msg += f"{status} שלב {tid}: {tdata['desc']}\n"
            bot.reply_to(m, msg, parse_mode="Markdown")
            return
        # /course <task_id> – requires payment and referrals
        task_id = parts[1]
        course_id = "bitcoin_mastery"
        student = db.get("students", {}).get(uid, {})
        enrolled = student.get("courses", {}).get(course_id, {})
        if not enrolled.get("paid"):
            bot.reply_to(m, "❌ יש לשלם קודם. שלח /pay")
            return
        task = db["courses"][course_id]["tasks"][task_id]
        required = task.get("required_refs", 0)
        refs = student.get("referral_count", 0)
        if refs < required:
            bot.reply_to(m, f"🔒 דרושות {required} הפניות. יש לך {refs}.")
            return
        code_file = task.get("code", "")
        if code_file:
            try:
                with open(os.path.expanduser(f"~/slh_clean/course_code/{code_file}")) as f:
                    code = f.read()
                bot.reply_to(m, f"```python\n{code[:3000]}\n```", parse_mode="Markdown")
            except:
                bot.reply_to(m, "⚠️ קוד לא זמין עדיין")
        else:
            bot.reply_to(m, f"📖 משימה: {task['desc']}")

    # ----- Bitcoin Mastery Course Commands -----

    @bot.message_handler(commands=['start_course'])
    def start_course(m):
        uid = str(m.from_user.id)
        db = load_db()
        if uid not in db.get("students", {}):
            bot.reply_to(m, "תחילה הירשם עם /join")
            return
        try:
            courses_def = json.load(open("courses.json"))
        except:
            bot.reply_to(m, "courses.json not found")
            return
        course_key = "bitcoin_mastery"
        if course_key not in courses_def:
            bot.reply_to(m, "הקורס לא זמין.")
            return
        student = db["students"][uid]
        if "courses" not in student:
            student["courses"] = {}
        if course_key in student["courses"]:
            bot.reply_to(m, "אתה כבר רשום לקורס. שלח /next להמשך.")
            return
        total_stages = len(courses_def[course_key]["stages"])
        student["courses"][course_key] = {
            "progress": 0,
            "current_stage": 1,
            "completed_stages": [],
            "total_stages": total_stages
        }
        save_db(db)
        bot.reply_to(m, "🎓 נרשמת לקורס ביטקוין מאסטרי!\nשלח /next לשיעור הראשון.")

    @bot.message_handler(commands=['next'])
    def next_lesson(m):
        uid = str(m.from_user.id)
        db = load_db()
        student = db.get("students", {}).get(uid)
        if not student or "bitcoin_mastery" not in student.get("courses", {}):
            bot.reply_to(m, "תחילה הירשם עם /start_course")
            return
        try:
            courses_def = json.load(open("courses.json"))
        except:
            bot.reply_to(m, "courses.json not found")
            return
        stages = courses_def["bitcoin_mastery"]["stages"]
        total_stages = len(stages)
        course_data = student["courses"]["bitcoin_mastery"]
        stage_id = course_data.get("current_stage", 1)
        if stage_id > total_stages:
            bot.reply_to(m, "🎉 סיימת את כל השלבים! כל הכבוד!")
            return
        stage = stages[stage_id - 1]
        lesson_file = stage["lesson"]
        if os.path.exists(lesson_file):
            with open(lesson_file, 'r') as f:
                text = f.read()
        else:
            text = f"שיעור {stage_id}: {stage['name']} (תוכן לא זמין כרגע)"
        completed = course_data.get("completed_stages", [])
        if stage_id not in completed:
            completed.append(stage_id)
            course_data["completed_stages"] = completed
            course_data["progress"] = int(len(completed) / total_stages * 100)
            course_data["current_stage"] = stage_id + 1
            save_db(db)
        bot.reply_to(m, f"📚 **{stage['name']}**\n\n{text}\n\nלשלב הבא – /next")

    @bot.message_handler(commands=['progress'])
    def progress(m):
        uid = str(m.from_user.id)
        db = load_db()
        student = db.get("students", {}).get(uid)
        if not student or "bitcoin_mastery" not in student.get("courses", {}):
            bot.reply_to(m, "אתה לא רשום לקורס. /start_course")
            return
        cd = student["courses"]["bitcoin_mastery"]
        total_stages = cd.get("total_stages", 3)
        done = len(cd.get("completed_stages", []))
        pct = cd.get("progress", 0)
        current = cd.get("current_stage", 1)
        msg = f"📊 התקדמות: {pct}% ({done}/{total_stages} שלבים)\n"
        if current <= total_stages:
            try:
                stages_def = json.load(open("courses.json"))["bitcoin_mastery"]["stages"]
                stage_name = stages_def[current-1]["name"]
            except:
                stage_name = "?"
            msg += f"בשלב: {current} – {stage_name}"
        else:
            msg += "סיימת את הקורס!"
        bot.reply_to(m, msg)

