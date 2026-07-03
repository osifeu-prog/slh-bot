import json, os

DB_PATH = os.path.expanduser("~/slh_clean/db.json")

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
