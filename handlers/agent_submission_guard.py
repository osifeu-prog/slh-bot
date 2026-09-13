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
                "💰 Credits are awarded only after approval.",
            )
            bot.send_message(
                8789977826,
                f"📦 Submission from {uid}: {agent_name}",
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
