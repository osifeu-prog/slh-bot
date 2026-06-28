import os, re

BOT = os.path.expanduser("~/slh_clean/bot.py")
with open(BOT, "r") as f:
    code = f.read()

new_handlers = r'''
# ==== STUDENT LEARNING SYSTEM ====

import json, time, datetime, os

DB_PATH = os.path.expanduser("~/slh_clean/db.json")

def load_db():
    with open(DB_PATH) as f:
        return json.load(f)

def save_db(db):
    with open(DB_PATH, "w") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

@bot.message_handler(commands=['register'])
def register_student(m):
    args = m.text.split(maxsplit=2)
    if len(args) < 3:
        bot.reply_to(m, "❌ שימוש: /register <שם> <קבוצה>")
        return
    name = args[1]
    group = args[2]
    uid = str(m.chat.id)
    db = load_db()
    if uid in db["students"]:
        bot.reply_to(m, "⚠️ אתה כבר רשום.")
        return
    db["students"][uid] = {
        "name": name,
        "group": group,
        "registered": datetime.datetime.now().isoformat()
    }
    save_db(db)
    bot.reply_to(m, f"✅ נרשמת בהצלחה, {name} ({group}).")

@bot.message_handler(commands=['courses'])
def list_courses(m):
    db = load_db()
    courses = db.get("courses", {})
    if not courses:
        bot.reply_to(m, "📭 אין קורסים זמינים כרגע.")
        return
    msg = "📚 **קורסים זמינים:**\n"
    for cid, cdata in courses.items():
        msg += f"• `{cid}` – {cdata['title']}\n"
    bot.reply_to(m, msg, parse_mode="Markdown")

@bot.message_handler(commands=['task'])
def show_task(m):
    args = m.text.split(maxsplit=2)
    if len(args) < 3:
        bot.reply_to(m, "❌ שימוש: /task <קורס> <מזהה משימה>")
        return
    course_id = args[1]
    task_id = args[2]
    db = load_db()
    course = db.get("courses", {}).get(course_id)
    if not course:
        bot.reply_to(m, "❌ קורס לא נמצא.")
        return
    task = course.get("tasks", {}).get(task_id)
    if not task:
        bot.reply_to(m, "❌ משימה לא נמצאה.")
        return
    desc = task.get("description", "אין תיאור")
    bot.reply_to(m, f"📌 **{course['title']}** – משימה `{task_id}`:\n{desc}", parse_mode="Markdown")

@bot.message_handler(commands=['submit'])
def submit_task(m):
    args = m.text.split(maxsplit=3)
    if len(args) < 4:
        bot.reply_to(m, "❌ שימוש: /submit <קורס> <מזהה משימה> <תשובה>")
        return
    course_id = args[1]
    task_id = args[2]
    answer = args[3]
    uid = str(m.chat.id)
    db = load_db()
    course = db.get("courses", {}).get(course_id)
    if not course or task_id not in course.get("tasks", {}):
        bot.reply_to(m, "❌ קורס או משימה לא קיימים.")
        return
    now = datetime.datetime.now().isoformat()
    db.setdefault("progress", {}).setdefault(uid, {}).setdefault(course_id, {"completed": [], "submissions": {}, "score": 0})
    db["progress"][uid][course_id]["submissions"][task_id] = {
        "answer": answer,
        "timestamp": now,
        "status": "pending",
        "feedback": ""
    }
    save_db(db)
    bot.reply_to(m, f"✅ הגשה התקבלה למשימה `{task_id}` בקורס `{course_id}`.\nסטטוס: ממתין לבדיקה.")

@bot.message_handler(commands=['myprogress'])
def my_progress(m):
    uid = str(m.chat.id)
    db = load_db()
    student = db.get("students", {}).get(uid)
    if not student:
        bot.reply_to(m, "❌ עליך להירשם קודם: /register <שם> <קבוצה>")
        return
    progress = db.get("progress", {}).get(uid, {})
    if not progress:
        bot.reply_to(m, "📭 אין התקדמות עדיין.")
        return
    msg = f"📊 התקדמות של {student['name']}:\n"
    for course_id, pdata in progress.items():
        course = db.get("courses", {}).get(course_id, {})
        title = course.get("title", course_id)
        completed = len(pdata.get("completed", []))
        total = len(course.get("tasks", {}))
        submissions = len(pdata.get("submissions", {}))
        msg += f"• {title}: {submissions}/{total} הוגשו, {completed} אושרו\n"
    bot.reply_to(m, msg)

# ==== TEACHER COMMANDS ====

@bot.message_handler(commands=['add_course'])
def add_course(m):
    args = m.text.split(maxsplit=2)
    if len(args) < 3:
        bot.reply_to(m, "❌ שימוש: /add_course <מזהה> <שם הקורס>")
        return
    cid = args[1]
    title = args[2]
    db = load_db()
    if cid in db.get("courses", {}):
        bot.reply_to(m, "⚠️ קורס עם מזהה זה כבר קיים.")
        return
    db.setdefault("courses", {})[cid] = {"title": title, "tasks": {}}
    save_db(db)
    bot.reply_to(m, f"✅ קורס `{cid}` – **{title}** נוסף.", parse_mode="Markdown")

@bot.message_handler(commands=['add_task'])
def add_task(m):
    args = m.text.split(maxsplit=3)
    if len(args) < 4:
        bot.reply_to(m, "❌ שימוש: /add_task <קורס> <מזהה משימה> <תיאור>")
        return
    course_id = args[1]
    task_id = args[2]
    desc = args[3]
    db = load_db()
    if course_id not in db.get("courses", {}):
        bot.reply_to(m, "❌ קורס לא קיים.")
        return
    db["courses"][course_id].setdefault("tasks", {})[task_id] = {"description": desc}
    save_db(db)
    bot.reply_to(m, f"✅ משימה `{task_id}` נוספה לקורס `{course_id}`.")

@bot.message_handler(commands=['review'])
def review_submissions(m):
    args = m.text.split()
    if len(args) < 3:
        bot.reply_to(m, "❌ שימוש: /review <student_id> <course_id>")
        return
    student_id = args[1]
    course_id = args[2]
    db = load_db()
    progress = db.get("progress", {}).get(student_id, {}).get(course_id)
    if not progress:
        bot.reply_to(m, "❌ אין הגשות לסטודנט/קורס זה.")
        return
    subs = progress.get("submissions", {})
    if not subs:
        bot.reply_to(m, "📭 אין הגשות.")
        return
    msg = f"📋 הגשות של {student_id} בקורס {course_id}:\n"
    for task_id, data in subs.items():
        status = data.get("status", "pending")
        answer = data.get("answer", "")[:50] + ("..." if len(data.get("answer",""))>50 else "")
        msg += f"• {task_id}: \"{answer}\" [{status}]\n"
    msg += "\nלעדכון סטטוס: /approve <student_id> <course_id> <task_id>"
    bot.reply_to(m, msg)

@bot.message_handler(commands=['approve'])
def approve_task(m):
    args = m.text.split()
    if len(args) < 4:
        bot.reply_to(m, "❌ שימוש: /approve <student_id> <course_id> <task_id>")
        return
    student_id, course_id, task_id = args[1], args[2], args[3]
    db = load_db()
    try:
        sub = db["progress"][student_id][course_id]["submissions"][task_id]
    except KeyError:
        bot.reply_to(m, "❌ הגשה לא נמצאה.")
        return
    sub["status"] = "approved"
    comp = db["progress"][student_id][course_id].setdefault("completed", [])
    if task_id not in comp:
        comp.append(task_id)
    save_db(db)
    bot.reply_to(m, f"✅ אושר: {student_id} – {task_id}")

# ===== END LEARNING SYSTEM =====
'''

# Remove old learning system block if exists
code = re.sub(r'# ==== STUDENT LEARNING SYSTEM ====.*?# ===== END LEARNING SYSTEM =====', '', code, flags=re.DOTALL)

loop_pos = code.find("while True:")
if loop_pos == -1:
    print("❌ while True not found")
    exit(1)

code = code[:loop_pos] + new_handlers + "\n" + code[loop_pos:]

with open(BOT, "w") as f:
    f.write(code)

print("✅ Handlers added successfully.")
