from state.reputation_service import reward_user
from state.reputation_audit import record_reward


def register(bot, is_admin_func=None):

    if is_admin_func is None:
        def is_admin_func(message):
            return False

    @bot.message_handler(commands=["reward"])
    def reward_command(message):

        if not is_admin_func(message):
            bot.reply_to(message, "⛔ Admin only")
            return

        parts = message.text.split()

        if len(parts) != 3:
            bot.reply_to(
                message,
                "Usage: /reward USER_ID ACTION"
            )
            return

        user_id = parts[1]
        action = parts[2]

        result = reward_user(
            user_id,
            action,
            {
                "source": "telegram_admin",
                "admin": message.from_user.id
            }
        )

        if "error" in result:
            bot.reply_to(
                message,
                f"❌ {result['error']}"
            )
            return

        record_reward(
            message.from_user.id,
            user_id,
            action
        )

        bot.reply_to(
            message,
            f"✅ Reputation added\n"
            f"User: {user_id}\n"
            f"Score: {result['score']}"
        )
