from core import economy_bridge
import state_manager
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

def register_learning_path(bot):
    @bot.message_handler(commands=['course_slh'])
    def course_slh(m):
        uid = str(m.from_user.id)
        db = state_manager.load_db()
        user = db.get("users", {}).get(uid, {})
        if not user:
            bot.send_message(m.chat.id, "❌ Please /join first.")
            return
        lessons = [
            ("ברוכים הבאים ל-SLH OS", "מערכת ההפעלה שלכם ללימוד, בניית סוכנים, וכלכלה דיגיטלית."),
            ("פקודות בסיסיות", "/help – תפריט פקודות\n/balance – יתרה\n/buy – רכישת כלים"),
            ("סוכנים חכמים", "/agent_create <name> – צור סוכן\n/agents – רשימת סוכנים"),
            ("כלכלה ותשלומים", "/pay – רכישת Credits\n/referral – הזמן חברים וקבל תגמולי הפניה לפי מדיניות המערכת"),
            ("בניית סוכן משלך", "צור סוכן, תכנת אותו, והגש אותו לשוק!\n/agent_submit <agent_name>"),
            ("הגשה ושוק", "לאחר ההגשה, הסוכן שלך ייבדק.\nאם יאושר, תקבל תגמול והוא יופיע ב-/market!")
        ]
        markup = InlineKeyboardMarkup(row_width=1)
        for i, (title, _) in enumerate(lessons):
            markup.add(InlineKeyboardButton(f"{i+1}. {title}", callback_data=f"course_slh_{i}"))
        bot.send_message(m.chat.id, "📚 **SLH OS Basics** – בחר שיעור:", reply_markup=markup, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("course_slh_"))
    def course_slh_callback(call):
        index = int(call.data.split("_")[-1])
        lessons = [
            ("ברוכים הבאים ל-SLH OS", "מערכת ההפעלה שלכם ללימוד, בניית סוכנים, וכלכלה דיגיטלית."),
            ("פקודות בסיסיות", "/help – תפריט פקודות\n/balance – יתרה\n/buy – רכישת כלים"),
            ("סוכנים חכמים", "/agent_create <name> – צור סוכן\n/agents – רשימת סוכנים"),
            ("כלכלה ותשלומים", "/pay – רכישת Credits\n/referral – הזמן חברים וקבל תגמולי הפניה לפי מדיניות המערכת"),
            ("בניית סוכן משלך", "צור סוכן, תכנת אותו, והגש אותו לשוק!\n/agent_submit <agent_name>"),
            ("הגשה ושוק", "לאחר ההגשה, הסוכן שלך ייבדק.\nאם יאושר, תקבל תגמול והוא יופיע ב-/market!")
        ]
        title, content = lessons[index]
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"📖 **{title}**\n\n{content}",
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id)

    # 4. Admin: Approve/Reject submissions
    @bot.message_handler(commands=['agent_reject'])
    def agent_reject(m):
        from admin_utils import is_admin
        if not is_admin(m):
            bot.reply_to(m, "⛔ Admin only")
            return
        parts = m.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /agent_reject <submission_id>")
            return
        try:
            sub_id = int(parts[1])
        except:
            bot.reply_to(m, "Invalid ID.")
            return
        db = state_manager.load_db()
        submissions = db.get("agent_submissions", [])
        if sub_id < 0 or sub_id >= len(submissions):
            bot.reply_to(m, "Submission not found.")
            return
        sub = submissions.pop(sub_id)
        state_manager.save_db(db)
        bot.reply_to(m, f"❌ Agent '{sub['agent_name']}' rejected.")
        bot.send_message(sub["uid"], f"❌ הסוכן '{sub['agent_name']}' נדחה. נסה שוב עם שיפור.")

    # 5. List pending submissions (admin)
    @bot.message_handler(commands=['agent_submissions'])
    def agent_submissions(m):
        from admin_utils import is_admin
        if not is_admin(m):
            bot.reply_to(m, "⛔ Admin only")
            return
        db = state_manager.load_db()
        submissions = db.get("agent_submissions", [])
        if not submissions:
            bot.reply_to(m, "No pending submissions.")
            return
        msg = "📋 **Pending Submissions:**\n"
        for i, sub in enumerate(submissions):
            msg += f"{i}: {sub['agent_name']} by {sub['uid']}\n"
        bot.reply_to(m, msg.strip())

    @bot.message_handler(commands=['setname'])
    def setname(m):
        parts = m.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /setname <new_name>")
            return
        new_name = parts[1].strip()
        uid = str(m.from_user.id)
        db = state_manager.load_db()
        user = db.setdefault("users", {}).setdefault(uid, {"name": "אוסיף"})
        user["name"] = new_name
        state_manager.save_db(db)
        bot.reply_to(m, f"✅ Your name is now {new_name}.")
