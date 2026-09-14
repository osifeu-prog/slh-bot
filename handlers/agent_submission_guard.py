from core import agent_submission_service


def register(bot):
    @bot.message_handler(commands=["agent_submit"])
    def agent_submit_guard(m):
        uid = str(m.from_user.id)
        parts = m.text.split(maxsplit=1)

        if len(parts) < 2:
            bot.send_message(m.chat.id, "Usage: /agent_submit <agent_name>")
            return

        agent_name = parts[1].strip()

        try:
            result = agent_submission_service.submit_agent(
                uid=uid,
                agent_name=agent_name,
                meta={
                    "source": "learning_path",
                    "telegram_user_id": uid,
                },
            )
            bot.send_message(
                m.chat.id,
                f"✅ Agent '{agent_name}' submitted for review.\n"
                f"🆔 Submission: {result['submission_id']}\n"
                "💰 Credits are awarded only after approval.",
            )
            bot.send_message(
                8789977826,
                f"📦 Submission from {uid}: {agent_name}\n"
                f"🆔 {result['submission_id']}",
            )
        except ValueError as e:
            if str(e) == "SUBMISSION_ALREADY_PENDING":
                bot.send_message(m.chat.id, "⏳ This agent is already pending review.")
            elif str(e) == "USER_NOT_FOUND":
                bot.send_message(m.chat.id, "❌ Please /join first.")
            else:
                bot.send_message(m.chat.id, "❌ Submission rejected safely.")
        except Exception as e:
            bot.send_message(m.chat.id, "❌ Submission failed safely.")
            print(f"[AGENT_SUBMISSION_GUARD] error: {e}")

    @bot.message_handler(commands=["agent_approve"])
    def agent_approve_guard(m):
        from admin_utils import is_admin

        if not is_admin(m):
            bot.reply_to(m, "⛔ Admin only")
            return

        parts = m.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /agent_approve <submission_id>")
            return

        try:
            result = agent_submission_service.approve_agent_submission(
                parts[1].strip(),
                meta={
                    "source": "learning_path",
                    "approved_by": str(m.from_user.id),
                },
            )
            bot.reply_to(
                m,
                f"✅ Agent '{result['agent_name']}' approved and added to /market!\n"
                f"💰 Creator received +{result['reward']} Credits.",
            )
            bot.send_message(
                result["creator_uid"],
                f"🎉 Agent '{result['agent_name']}' approved!\n"
                f"💰 +{result['reward']} Credits",
            )
        except ValueError as e:
            if str(e) in {"SUBMISSION_NOT_FOUND", "SUBMISSION_NOT_PENDING", "AGENT_ALREADY_APPROVED"}:
                bot.reply_to(m, f"❌ Approval rejected safely: {e}")
            else:
                bot.reply_to(m, "❌ Approval failed safely.")
            print(f"[AGENT_SUBMISSION_GUARD] approval error: {e}")
        except Exception as e:
            bot.reply_to(m, "❌ Approval failed safely.")
            print(f"[AGENT_SUBMISSION_GUARD] approval error: {e}")
