import json, os
from core import profile_manager

DB_PATH = "state/db.json"

def load_db():
    with open(DB_PATH) as f:
        return json.load(f)

def save_db(db):
    with open(DB_PATH, "w") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

def register_course_handlers(bot):
    # /pay moved to payment_handler.py
    # Single source payment handler
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
        user = profile_manager.get_user(uid)

        if not user.get('joined'):
            bot.reply_to(m, 'תחילה הירשם עם /join')
            return

        try:
            with open('courses.json', 'r', encoding='utf-8') as f:
                courses_def = json.load(f)
        except Exception:
            bot.reply_to(m, 'courses.json not found')
            return

        course_key = 'bitcoin_mastery'
        course = courses_def.get(course_key)
        if not course:
            bot.reply_to(m, 'הקורס לא זמין.')
            return

        total_stages = len(course.get('stages', []))
        courses = user.get('academy', {}).get('courses', {})

        if course_key in courses:
            bot.reply_to(m, 'אתה כבר רשום לקורס. שלח /next להמשך.')
            return

        profile_manager.update_user(uid, {
            'academy': {
                'courses': {
                    course_key: {
                        'stage': 0,
                        'completed': [],
                        'total_stages': total_stages,
                    }
                }
            }
        })

        bot.reply_to(
            m,
            '🎓 נרשמת לקורס ביטקוין מאסטרי!\n'
            'שלח /next לשיעור הראשון.'
        )
    @bot.message_handler(commands=['next'])
    def next_lesson(m):
        uid = str(m.from_user.id)
        user = profile_manager.get_user(uid)

        if not user.get('joined'):
            bot.reply_to(m, 'תחילה הירשם עם /join')
            return

        try:
            with open('courses.json', 'r', encoding='utf-8') as f:
                courses_def = json.load(f)
        except Exception:
            bot.reply_to(m, 'courses.json not found')
            return

        course_key = 'bitcoin_mastery'
        course = courses_def.get(course_key)
        if not course:
            bot.reply_to(m, 'הקורס לא זמין.')
            return

        stages = course.get('stages', [])
        total_stages = len(stages)

        course_data = (
            user.get('academy', {})
                .get('courses', {})
                .get(course_key)
        )

        if not course_data:
            bot.reply_to(m, 'תחילה הירשם עם /start_course')
            return

        next_stage = course_data.get('stage', 0) + 1

        if next_stage > total_stages:
            bot.reply_to(m, '🎉 סיימת את כל השלבים! כל הכבוד!')
            return

        stage = stages[next_stage - 1]
        lesson_file = stage.get('lesson')

        if lesson_file and os.path.exists(lesson_file):
            with open(lesson_file, 'r', encoding='utf-8') as f:
                lesson_text = f.read()
        else:
            lesson_text = (
                f"שיעור {next_stage}: "
                f"{stage.get('name', 'ללא שם')} "
                "(תוכן לא זמין כרגע)"
            )

        result = profile_manager.complete_course_stage(
            uid, course_key, next_stage
        )

        completed = list(result.get('completed', []))
        progress = (
            int(len(completed) / total_stages * 100)
            if total_stages else 0
        )

        bot.reply_to(
            m,
            f"📚 {stage.get('name', 'ללא שם')}\n\n"
            f"{lesson_text}\n\n"
            f"📊 התקדמות: {progress}%\n"
            f"לשלב הבא – /next",
            parse_mode='Markdown'
        )
    # /progress moved to handlers/academy_handler.py
    # Single source academy progress handler
