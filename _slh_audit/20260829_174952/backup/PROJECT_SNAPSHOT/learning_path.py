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
            bot.send_message(m.chat.id, "â Please /join first.")
            return
        lessons = [
            ("××¨×××× ××××× ×-SLH OS", "××¢×¨××ª ×××¤×¢×× ×©××× ××××××, ×× ×××ª ×¡××× ××, ×××××× ××××××××ª."),
            ("×¤×§××××ª ××¡××¡×××ª", "/help â ×ª×¤×¨×× ×¤×§××××ª\n/balance â ××ª×¨×\n/buy â ×§× ×××ª ××××"),
            ("×¡××× ×× ×××××", "/agent_create <name> â ×¦××¨ ×¡×××\n/agents â ×¨×©×××ª ×¡××× ××"),
            ("××××× ××ª×©×××××", "/pay â ×§× ×××ª Credits\n/referral â ×××× ×××¨×× ×××¨××× 85% ×¢×××"),
            ("×× ×××ª ×¡××× ××©××", "×¦××¨ ×¡×××, ×ª×× ×ª ×××ª×, ××××© ×××ª× ××©××§!\n/agent_submit <agent_name>"),
            ("×××©× ××©××§", "××××¨ ××××©×, ××¡××× ×©×× ×××××§.\n×× ××××©×¨, ×ª×§×× 50 Credits ×××× ×××¤××¢ ×-/market!")
        ]
        markup = InlineKeyboardMarkup(row_width=1)
        for i, (title, _) in enumerate(lessons):
            markup.add(InlineKeyboardButton(f"{i+1}. {title}", callback_data=f"course_slh_{i}"))
        bot.send_message(m.chat.id, "ð **SLH OS Basics** â ×××¨ ×©××¢××¨:", reply_markup=markup, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("course_slh_"))
    def course_slh_callback(call):
        index = int(call.data.split("_")[-1])
        lessons = [
            ("××¨×××× ××××× ×-SLH OS", "××¢×¨××ª ×××¤×¢×× ×©××× ××××××, ×× ×××ª ×¡××× ××, ×××××× ××××××××ª."),
            ("×¤×§××××ª ××¡××¡×××ª", "/help â ×ª×¤×¨×× ×¤×§××××ª\n/balance â ××ª×¨×\n/buy â ×§× ×××ª ××××"),
            ("×¡××× ×× ×××××", "/agent_create <name> â ×¦××¨ ×¡×××\n/agents â ×¨×©×××ª ×¡××× ××"),
            ("××××× ××ª×©×××××", "/pay â ×§× ×××ª Credits\n/referral â ×××× ×××¨×× ×××¨××× 85% ×¢×××"),
            ("×× ×××ª ×¡××× ××©××", "×¦××¨ ×¡×××, ×ª×× ×ª ×××ª×, ××××© ×××ª× ××©××§!\n/agent_submit <agent_name>"),
            ("×××©× ××©××§", "××××¨ ××××©×, ××¡××× ×©×× ×××××§.\n×× ××××©×¨, ×ª×§×× 50 Credits ×××× ×××¤××¢ ×-/market!")
        ]
        title, content = lessons[index]
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"ð **{title}**\n\n{content}",
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id)

    @bot.message_handler(commands=['agent_submit'])
    def agent_submit(m):
        from core import economy_service

        uid = str(m.from_user.id)
        parts = m.text.split(maxsplit=1)

        if len(parts) < 2:
            bot.send_message(
                m.chat.id,
                "Usage: /agent_submit <agent_name>"
            )
            return

        agent_name = parts[1].strip()

        try:
            result = economy_service.submit_agent(
                uid=uid,
                agent_name=agent_name,
                reward=10,
                meta={
                    "source": "learning_path",
                    "telegram_user_id": uid,
                },
            )

            bot.send_message(
                m.chat.id,
                f"✅ Agent '{agent_name}' submitted!\n"
                f"💰 +{result['reward']} Credits"
            )

            bot.send_message(
                8789977826,
                f"📦 Submission from {uid}: {agent_name}"
            )

        except Exception as e:
            bot.send_message(
                m.chat.id,
                "❌ Submission failed safely."
            )
            print(
                f"[LEARNING_PATH] agent_submit error: {e}"
            )

    # 4. Admin: Approve/Reject submissions
    @bot.message_handler(commands=['agent_approve'])
    def agent_approve(m):
        from admin_utils import is_admin
        from core import economy_service

        if not is_admin(m):
            bot.reply_to(m, "⛔ Admin only")
            return

        parts = m.text.split(maxsplit=1)

        if len(parts) < 2:
            bot.reply_to(
                m,
                "Usage: /agent_approve <submission_id>"
            )
            return

        try:
            sub_id = int(parts[1])
        except Exception:
            bot.reply_to(m, "Invalid ID.")
            return

        try:
            result = economy_service.approve_agent_submission(
                submission_id=sub_id,
                reward=40,
                meta={
                    "source": "learning_path",
                    "approved_by": str(m.from_user.id),
                },
            )

            bot.reply_to(
                m,
                f"✅ Agent '{result['agent_name']}' approved "
                f"and added to /market!\n"
                f"💰 Creator received +{result['reward']} Credits."
            )

            bot.send_message(
                result["creator_uid"],
                f"🎉 Agent '{result['agent_name']}' approved!\n"
                f"💰 +{result['reward']} Credits"
            )

        except Exception as e:
            bot.reply_to(
                m,
                "❌ Approval failed safely."
            )
            print(
                f"[LEARNING_PATH] agent_approve error: {e}"
            )

    @bot.message_handler(commands=['agent_reject'])
    def agent_reject(m):
        from admin_utils import is_admin
        if not is_admin(m):
            bot.reply_to(m, "âï¸ Admin only")
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
        bot.reply_to(m, f"â Agent '{sub['agent_name']}' rejected.")
        bot.send_message(sub["uid"], f"â ××¡××× '{sub['agent_name']}' × ×××. × ×¡× ×©×× ×¢× ×©××¤××¨.")

    # 5. List pending submissions (admin)
    @bot.message_handler(commands=['agent_submissions'])
    def agent_submissions(m):
        from admin_utils import is_admin
        if not is_admin(m):
            bot.reply_to(m, "âï¸ Admin only")
            return
        db = state_manager.load_db()
        submissions = db.get("agent_submissions", [])
        if not submissions:
            bot.reply_to(m, "No pending submissions.")
            return
        msg = "ð **Pending Submissions:**\n"
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
        user = db.setdefault("users", {}).setdefault(uid, {"name": "×××¡××£"})
        user["name"] = new_name
        state_manager.save_db(db)
        bot.reply_to(m, f"â Your name is now {new_name}.")

